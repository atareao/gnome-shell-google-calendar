#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import codecs
import sys
import getopt
import time as ptime
from datetime import datetime, timedelta
from threading import Thread
from time import mktime, sleep

import gdata.calendar.client

import dbus
import dbus.mainloop.glib
import dbus.service
import gtk
import iso8601
import calendar
import os

# Append the /usr/lib path for oauth and config libraries
# as the installer places them
sys.path.insert(0, "/usr/lib/gnome-shell-google-calendar")

import oauth
import config
#  change to "True" to get debugging messages
debug = False


SHOW_SHORT_CALENDAR_TITLE = True


def write_traceback(f):
    '''Wrapper that catches any tracebacks that are found and writes them to
    stdout.  This is because Gnome isn't so good about telling you.'''

    def wrapper(*args, **kwargs):
        try:
            if debug:
                print dir(f)
                print 'Calling: %s with args=%s kwargs=%s' % (f, args, kwargs)
            ret = f(*args, **kwargs)
            if debug:
                print 'Returning from %s: %s' % (f, ret)
            return ret
        except Exception as e:
            import traceback
            print '*** Exception:', str(e)
            traceback.print_exc()
            raise
    return wrapper


def get_month_key(date, first_day_of_week=7):
    """Returns range of dates displayed on calendars for `date`'s month.
    Parameters:
     - `date`: definies month which's range to return
     - `first_day_of_week`: integer representing first day of week used by
                            calendar; Monday -> 1, ..., Sunday -> 7
    """
    month_calendar = list(calendar.Calendar(first_day_of_week - 1
            ).itermonthdates(date.year, date.month))

    start_date = datetime(month_calendar[0].year, month_calendar[0].month,
            month_calendar[0].day)
    end_date = datetime(month_calendar[-1].year, month_calendar[-1].month,
            month_calendar[-1].day, hour=23, minute=59, second=59)

    return (int(mktime(start_date.timetuple())),
            int(mktime(end_date.timetuple())))


class MonthEvents(object):
    """
    Caches events of month
    """
    def __init__(self, key, events):
        self.start = key[0]
        self.end = key[1]
        self.events = []
        for event in events:
            self.add_event(event)
        self.last_update = datetime.now()

    def delete(self):
        del self.start
        del self.end
        del self.events[:]
        del self.last_update

    def add_event(self, event):
        """Adds event to events and gnome_events if in month's range"""
        start = self.start
        end = self.end
        if (event.start_time >= start and event.start_time < end) or\
                (event.start_time <= start and event.end_time - 1 > start):
            self.events.append(event)

    def updated(self):
        self.last_update = datetime.now()

    def needs_update(self, timeout=timedelta(minutes=10)):
        return self.last_update + timeout < datetime.now()

    def get_key(self):
        return self.start, self.end

    def get_prev_month_key(self):
        probe_date = self.get_start_date() - timedelta(days=1)
        return get_month_key(probe_date)

    def get_next_month_key(self):
        probe_date = self.get_end_date() + timedelta(days=1)
        return get_month_key(probe_date)

    def get_start_date(self):
        return datetime.fromtimestamp(self.start)

    def get_end_date(self):
        return datetime.fromtimestamp(self.end)

    @write_traceback
    def get_gnome_events(self):
        '''Return a list of events to display on the calendar.  This function
        removes duplicate events.'''

        #  join events that have the same key
        events_by_key = {}
        for event in self.events:
            event_key = event.get_key()

            event_list = events_by_key.get(event_key) or []
            events_by_key[event_key] = event_list
            event_list.append(event)

        #  collect events
        ret = []
        for events in events_by_key.values():
            gnome_event = list(events[0].as_gnome_event())
            if SHOW_SHORT_CALENDAR_TITLE:
                gnome_event[1] += ' (%s)' % (
                        '/'.join([x.get_short_calendar_title()
                                for x in events]),)
            ret.append(gnome_event)

        return ret

    def __repr__(self):
        return u'<MonthEvents: %s, with %d events>' % (
                (self.get_start_date() + timedelta(days=10)).strftime('%B %Y'),
                len(self.events))


class Event(object):
    def __init__(self, event_id, title, start_time, end_time, allday=False,
            calendar_title=''):
        self.event_id = event_id
        self.title = title
        self.start_time = start_time
        self.end_time = end_time
        self.allday = allday
        self.calendar_title = calendar_title

    @write_traceback
    def get_short_calendar_title(self):
        if len(self.calendar_title.split()) > 1:
            return ''.join([x[0] for x in
                    unicode(self.calendar_title).split()])

        return unicode(self.calendar_title)[:2]

    def get_key(self):
        return self.title, self.allday, self.start_time

    @write_traceback
    def as_gnome_event(self):
        return ('',                                     # uid
                self.title if self.title else '',       # summary
                '',                                     # description
                self.allday,                            # allDay
                self.start_time,                        # date
                self.end_time,                          # end
                {})                                     # extras

    def __repr__(self):
        return '<Event: %r>' % (self.title)


class CalendarServer(dbus.service.Object):
    busname = 'org.gnome.Shell.CalendarServer'
    object_path = '/org/gnome/Shell/CalendarServer'

    def __init__(self, client):
        bus = dbus.service.BusName(self.busname,
                                        bus=dbus.SessionBus(),
                                        replace_existing=True)

        super(CalendarServer, self).__init__(bus, self.object_path)

        self.client = client
        self.calendars = self.get_calendars()

        # Events indexed by (since, until)
        self.months = {}

        # Make threading work
        gtk.gdk.threads_init()

        # Thread used to fetch events in background
        self.updater = Thread()

        # Thread keeping events updated
        self.scheduler = Thread(target=self.scheduler,
                                args=(timedelta(minutes=1),))
        self.scheduler.daemon = True
        self.scheduler.start()

    def needs_update(self):
        current_month_key = get_month_key(datetime.now())
        if not current_month_key in self.months:
            return True
        if self.months[current_month_key].needs_update(timedelta(minutes=2)):
            return True
        return False

    def scheduler(self, timeout):
        while 1:
            sleep(timeout.seconds)
            print 'Checking if actual month events need update...'
            if self.needs_update():
                while self.updater.is_alive():
                    sleep(1)
                    print 'Scheduler waiting for updater thread to end...'
                if self.needs_update():
                    print 'Scheduler starts updater thread...'
                    self.updater = Thread(target=self.update_months_events,
                                        args=(datetime.now(), True))
                    self.updater.start()
                else:
                    print 'Updater thread updated actual month'
            else:
                print 'No need for update'

    def get_excludes(self, filename):
        '''Gets a list of calendars to exclude'''
        with codecs.open(filename, 'r', 'utf-8') as fp:
            return frozenset(line.strip() for line in fp)

    def get_calendars(self):
        while True:
            try:
                feed = self.client.GetAllCalendarsFeed()
                break
            except Exception as e:
                print '*** Exception:', str(e)
                print ('Error retrieving all calendars. '
                        'Trying again in 5 seconds...')
                sleep(5)
                continue

        # Load excluded calendars from excludes file
        excludes = set()
        for filename in ('excludes',
                os.path.expanduser('~/.gnome-shell-google-calendar-excludes'), '/etc/gnome-shell-google-calendar/excludes'):
            if os.path.exists(filename):
                excludes |= self.get_excludes(filename)

        calendars = []
        urls = set()

        print feed.title.text + ':'

        for calendar in feed.entry:
            if calendar.overridename:
                title = calendar.overridename.value
            else:
                title = calendar.title.text
            url = calendar.content.src

            if title in excludes:
                continue

            if not url in urls:
                print '  ', title
                if debug:
                    print '    ', url
                urls.add(url)
                calendars.append((title, url))

        return calendars

    def parse_time(self, timestr):
        try:
            time = datetime.strptime(timestr, '%Y-%m-%d')
            time = time.timetuple()
            allday = True
        except ValueError:
            time = iso8601.parse_date(timestr)
            time = ptime.localtime(calendar.timegm(
                time.utctimetuple()[:-1] + (-1,)))
            allday = False

        timestamp = int(mktime(time))

        return (timestamp, allday)

    @write_traceback
    def update_months_events(self, probe_date, in_thread=False,
                            months_back=12, months_ahead=12):
        if in_thread:
            prefix = '      <<<<THREAD>>>>  '
        else:
            prefix = '    '

        print prefix, 'Update months events around:', \
                probe_date.strftime('%B %Y'), '| months_back', months_back, \
                '| months_ahead', months_ahead

        months = {}

        # init asked month events
        key = initial_month_key = get_month_key(probe_date)
        months[key] = MonthEvents(key, [])

        # init previous months events
        for i in range(0, months_back):
            key = months[key].get_prev_month_key()
            months[key] = MonthEvents(key, [])
        # date for google query start limit
        min_date = months[key].get_start_date()

        # init next months events
        key = initial_month_key
        for i in range(0, months_ahead):
            key = months[key].get_next_month_key()
            months[key] = MonthEvents(key, [])
        # date for google query end limit
        max_date = months[key].get_end_date()

        # Get events from all calendars
        for calendar_title, feed_url in self.calendars:
            print prefix, 'Getting events from', calendar_title, '...'

            query = gdata.calendar.client.CalendarEventQuery()
            query.feed = feed_url
            query.start_min = min_date.strftime('%Y-%m-%d')
            query.start_max = max_date.strftime('%Y-%m-%d')
            query.max_results = 2 ** 31 - 1
            feed = self.client.GetCalendarEventFeed(feed_url, q=query)

            for event in feed.entry:
                event_id = event.id.text
                title = event.title.text

                if debug:
                    print '%s Event: title=%s' % (prefix, repr(title))

                for when in event.when:
                    #print dir(when)
                    if debug:
                        print '%s    start_time=%s end_time=%s' % (prefix,
                                repr(when.start), repr(when.end))

                    allday = False
                    start, allday = self.parse_time(when.start)
                    end = self.parse_time(when.end)[0]

                    e = Event(event_id, title, start, end, allday,
                            calendar_title)
                    for month in months.values():
                        month.add_event(e)

        # Replace old months events by new ones
        # TODO repair deletion if python doesn't do it
        for key, month in months.items():
            month.updated()
#            print '!'
#            self.months[key].delete()
#            print '!'
#            del self.months[key]
            self.months[key] = month

        print prefix, '#Updated events since', \
                (min_date + timedelta(days=10)).strftime('%B %Y'), \
                'until', (max_date - timedelta(days=10)).strftime('%B %Y')

    @write_traceback
    def need_update_near(self, key, months_back=6, months_ahead=6):
        """Check if months around month declared by `key` need update or not
        yet fetched"""

        #  get a list of months to check
        months_to_check = [key]
        for i in range(months_back):
            months_to_check.append(
                    self.months[months_to_check[-1]].get_prev_month_key())
        months_to_check.reverse()
        for i in range(months_ahead):
            months_to_check.append(
                    self.months[months_to_check[-1]].get_next_month_key())

        #  Do any of those months need updating
        for month_key in months_to_check:
            month = self.months.get(month_key)
            if not month or (month and month.needs_update()):
                return True

        # All up to date
        return False

    @dbus.service.method('org.gnome.Shell.CalendarServer',
                         in_signature='xxb', out_signature='a(sssbxxa{sv})')
    def GetEvents(self, since, until, force_reload):
        since = int(since)
        until = int(until)
        force_reload = bool(force_reload)

        print "\nGetEvents(since=%s, until=%s, force_reload=%s)" % \
                (since, until, force_reload)

        probe_date = datetime.fromtimestamp(since) + timedelta(days=10)

        print '  Getting events for:', probe_date.strftime('%B %Y')

        key = get_month_key(probe_date)

        if not key in self.months:
            print '  Month not yet downloaded'
            while self.updater.is_alive():
                print '  Waiting for updater thread to end...'
                sleep(1)
            if not key in self.months:
                print '  Updating...'
                self.update_months_events(probe_date)
            else:
                print '  Month was downloaded by thread'
        elif (not self.updater.is_alive()) and self.need_update_near(key):
            print '  Old cache. Starting updater thread...'
            self.updater = Thread(target=self.update_months_events,
                                    args=(probe_date, True))
            self.updater.start()
        else:
            print '  Data loaded form cache'

        print ' #Returning', len(self.months[key].events), 'events...'

        return self.months[key].get_gnome_events()


if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    opts, args = getopt.getopt(sys.argv[1:], '', ['hide-cal', 'account='])
    account = None
    for o, a in opts:
        if o == '--hide-cal':
            SHOW_SHORT_CALENDAR_TITLE = False
        if o == '--account':
            account = a

    if not account:
        account = config.get('account')

    # Login
    client = None
    while not client:
        print "Logging in as '%s'..." % account
        try:
            client = oauth.oauth_login(account)
        except Exception:
            print 'Error logging in as \'%s\'' % account
            print ('\'%s\' may not be a GNOME online account. '
                    'A list of existing accounts is below.') % account
            print ('If you do not see a list of accounts, '
                    'then you first need to add one.')
            print ('For more information, see '
                    'http://library.gnome.org/users/gnome-help/stable/'
                    'accounts.html')
            try:
                account = oauth.oauth_prompt()
            except ValueError:
                print ('You have entered an invalid account number. '
                        'Please enter an integer.')
            config.set('account', account)

    myserver = CalendarServer(client)
    gtk.main()

'''
Created on 17.02.2012

@author: flocki
'''
import dbus
import gdata.calendar.client


def oauth_prompt():
    bus = dbus.SessionBus()
    online_accounts = bus.get_object('org.gnome.OnlineAccounts',
            '/org/gnome/OnlineAccounts')

    l = online_accounts.GetManagedObjects(
            dbus_interface='org.freedesktop.DBus.ObjectManager')

    accounts = []
    for account_info in l.values():
        if 'org.gnome.OnlineAccounts.Account' in account_info:
            email = str(account_info['org.gnome.OnlineAccounts.Account']
                    ['PresentationIdentity'])
            print "%d. %s" % (len(accounts), email)
            accounts.append(email)
    if len(accounts) == 1:
      return accounts[0]
    email = accounts[int(raw_input('Please choose the Account: '))]
    print "You choose '{0}'".format(email)
    return email


def oauth_login(email):
    bus = dbus.SessionBus()
    online_accounts = bus.get_object('org.gnome.OnlineAccounts',
            '/org/gnome/OnlineAccounts')

    l = online_accounts.GetManagedObjects(
            dbus_interface='org.freedesktop.DBus.ObjectManager')

    for account_path, account_info in l.items():
        if 'org.gnome.OnlineAccounts.Account' in account_info and \
                str(account_info['org.gnome.OnlineAccounts.Account']
                        ['PresentationIdentity']) == email:
            consumer_key = str(
                    account_info['org.gnome.OnlineAccounts.OAuthBased']
                    ['ConsumerKey'])
            consumer_secret = str(
                    account_info['org.gnome.OnlineAccounts.OAuthBased']
                    ['ConsumerSecret'])

            o = bus.get_object('org.gnome.OnlineAccounts', account_path)

            oauth_data = o.get_dbus_method('GetAccessToken',
                    'org.gnome.OnlineAccounts.OAuthBased')()

            access_token = str(oauth_data[0])
            access_token_secret = str(oauth_data[1])

            client = gdata.calendar.client.CalendarClient(
                    source='gnome-shell-google-calendar')
            client.auth_token = gdata.gauth.OAuthHmacToken(consumer_key,
                    consumer_secret, access_token, access_token_secret,
                    gdata.gauth.ACCESS_TOKEN)
            return client

    raise Exception

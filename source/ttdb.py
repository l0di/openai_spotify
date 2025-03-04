import os
import psycopg2
from dataclasses import dataclass, asdict
from datetime import datetime as dt
import threading
from loglib import logger
from flask_login import UserMixin

db_user = os.environ['DB_USER']
db_pass = os.environ['DB_PASS']
db_name = os.environ['DB_NAME']

@dataclass
class BaseDC:
  def dict(self):
    return {k: str(v) for k, v in asdict(self).items()}

@dataclass
class Playlist(BaseDC):
  phone_number: str
  playlist_id: str
  prompt: str
  success: int
  time_created: dt
  error_message: str
  public: int = 1
  deleted: int = 0

@dataclass
class Users(BaseDC):
  phone_number: str
  subscribed: int
  playlist_created: int = 0
  contact_sent: int = 0

@dataclass
class UserMessages(BaseDC):
  phone_number: str
  message: str


@dataclass
class UserPass(UserMixin, BaseDC):
  user_id: int
  email: str
  password: str
  name: str

  def get_id(self):
    return self.user_id


@dataclass
class SpotifyCreds(BaseDC):
  username: str
  access_token: str
  refresh_token: str

@dataclass 
class SpotifyPlaylistNames(BaseDC):
  name: str


class TTDB():
  def __init__(self):
    self.conn = psycopg2.connect(
      host='localhost', database=db_name,
      user=db_user, password=db_pass
    )
    self.cur = self.conn.cursor()
    self.lock = threading.Lock()
    self.subscriber_table = 'subscribers'
    self.playlist_table = 'playlist'
    self.user_table = 'users'
    self.user_messages = 'user_messages'
    self.spotify_users = 'spotify_users'
    self.playlist_names = 'playlist_names'
    self._create_tables()

  def close(self):
    self.cur.close()
    self.conn.close()

  def execute(self, cmd, *args):
    self.lock.acquire()
    try:
      self.cur.execute(cmd, args)
    except Exception as e:
      logger.info('DB exception: %s', e)

    self.conn.commit()
    self.lock.release()

    try:
      return self.cur.fetchall()
    except:
      return None

  def _create_tables(self):
    playlist = (
      f'create table if not exists {self.playlist_table} ('
        'phone_number varchar,'
        'playlist_id varchar (40),'
        'prompt varchar (300),'
        'success integer not null,'
        'time_created timestamp with time zone,'
        'error_message varchar (300),'
        'public integer,'
        'deleted integer'
        ');'
    )
    self.execute(playlist)

    users = (
      f'create table if not exists {self.user_table} ('
        'phone_number varchar primary key,'
        'subscribed int,'
        'playlist_created int,'
        'contact_sent int'
      ');'
    )
    self.execute(users)

    messages = (
      f'create table if not exists {self.user_messages} ('
        'phone_number varchar,'
        'message varchar (300)'
        ');'
    )
    self.execute(messages)

    subscribers = (
      f'create table if not exists {self.subscriber_table} ('
        'user_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,'
        'email varchar (75) unique,'
        'password varchar (110),'
        'name varchar (100)'
        ');'
    )
    self.execute(subscribers)

    users = (
      f'create table if not exists {self.spotify_users} ('
        'username varchar primary key,'
        'access_token varchar,'
        'refresh_token varchar'
      ');'
    )
    self.execute(users)

    pnames = (
      f'create table if not exists {self.playlist_names} ('
        'name varchar primary key'
      ');'
    )
    self.execute(pnames)

  def spotify_insert(self, args: dict):
    return self._table_insert(args, self.spotify_users)

  def user_insert(self, args: dict):
    return self._table_insert(args, self.user_table)

  def user_message_insert(self, args: dict):
    return self._table_insert(args, self.user_messages)

  def playlist_insert(self, args: dict):
    return self._table_insert(args, self.playlist_table)

  def subscriber_insert(self, args: dict):
    return self._table_insert(args, self.subscriber_table)

  def playlist_name_insert(self, args: dict):
    return self._table_insert(args, self.playlist_names)

  def _table_insert(self, args: dict, table_name: str):
    keys = ', '.join(list(args.keys()))
    values_ph = ', '.join(['%s'] * len(args))
    insert = (
      f'insert into {table_name} ({keys})'
      f'values ({values_ph})'
    )
    return self.execute(insert, *list(args.values()))

  def playlist_name_exists(self, name: str):
    q = f'select * from {self.playlist_names} where name = %s'
    return self.execute(q, (name))

  def playlists_per_user(self, number_id: str):
    q = f'select count(*) from {self.playlist_table} where phone_number = %s;'
    count = self.execute(q, (number_id))
    if not count:
      return 0
    return count[0][0]

  def spotify_user_exists(self, username: str):
    """Checks if username already in db."""
    q = f'select * from {self.spotify_users} where username = %s'
    return self.execute(q, (username))

  def spotify_update_user(self, username: str, access_token: str, refresh_token: str):
    """Update tokens for user."""
    q = (
      f'update {self.spotify_users} '
      'set access_token=%s, '
      'set refresh_token=%s, '
      'where username = %s;'
      )
    return self.execute(q, (access_token, refresh_token, username))

  def load_subscriber(self, user_id: str):
    """Load user given id."""
    q = f'select * from {self.subscriber_table} where user_id = %s'
    return self.execute(q, (user_id))

  def get_subscriber(self, email: str):
    """Check subscriber table for email."""
    q = f'select * from {self.subscriber_table} where email = %s'
    return self.execute(q, (email))

  def add_subscriber(self, subscriber):
    """Add user to subscriber table."""
    user = subscriber.dict()
    user.pop('user_id')
    return self.subscriber_insert(user)

  def get_user(self, phone_number: str) -> bool:
    q = f'select * from {self.user_table} where phone_number = %s'
    return self.execute(q, *[phone_number])

  def get_user_count(self) -> int:
    q = f'select count(*) from {self.user_table};'
    return self.execute(q)[0][0]

  def user_created_playlist(self, phone_number):
    q = (
      f'update {self.user_table} '
      'set playlist_created=1 '
      'where phone_number = %s;'
      )
    return self.execute(q, *[phone_number])

  def _test_playlist_insert(self):
    d = Playlist(
      phone_number = '+16093135446',
      playlist_id = '132EIn7jj8PsKw2AORasuS',
      prompt = 'make me a playlist "with" \'ambien\'t audio. music that will help me focus. super instrumental. study music but upbeat. high bpm. Similar to The Chemical Brothers or Justice or Fred again..',
      success = 1,
      time_created=dt.now(), 
      error_message= '')
    self.playlist_insert(d.dict())

    d = Users(
      phone_number='+16093135446', subscribed=1, playlist_created=0
    )
    self.user_insert(d.dict())

    d = UserMessages(
      phone_number='+16093135446', message='adfasdfasdfasd fuck'
    )
    self.user_message_insert(d.dict())

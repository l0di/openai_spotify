from chat import create_prompt, get_assistant_message, create_playlist_name_from_query
from spotify import SpotifyRequest, chatOutputToStructured
import argparse
import sys
from enum import Enum

class ERROR_CODES(Enum):
  NO_ERROR=0
  ERROR_NO_SPOTIFY_USER=1
  ERROR_CHAT_GPT=2
  ERROR_NO_SPOTIFY_RECS=3
  ERROR_NO_PLAYLIST_CREATE=4
  ERROR_OPENAI_SEX=5

def playlist_for_query(user_query: str):
  """Responds with tuple of (Error, Message)."""
  spot = SpotifyRequest()
  spot.reinit()
  if not spot.current_user():
    return ERROR_CODES.ERROR_NO_SPOTIFY_USER, None

  genres = spot.get_genre_seeds()['genres']
  attributes = spot.get_attributes()
  msgs = create_prompt(user_query, attrs=attributes, genres=genres)
  chat_outputs = get_assistant_message(msgs)
  msgs = create_playlist_name_from_query(user_query)
  pname = get_assistant_message(msgs, temperature=.5)
  print('chat gpt playlist name: ', pname)
  if not chat_outputs:
    return ERROR_CODES.ERROR_CHAT_GPT, None
  print('gpt output: ', chat_outputs)
  s_genres, s_artists, s_songs, s_attrs = chatOutputToStructured(chat_outputs, attributes=attributes)
  if not any([s_genres, s_artists, s_songs, s_attrs]):
    return ERROR_CODES.ERROR_OPENAI_SEX, None
  s_artists = s_artists + list(s_songs.values())
  print('before genres: ', s_genres)
  s_genres = [g for g in s_genres if g in genres]
  print('after genres: ', s_genres)
  print('artists: ', s_artists)
  print('songs: ', s_songs)
  print('attributes: ', s_attrs)
  s_artists = spot.IdsForArtists(s_artists)
  s_songs = spot.IdsForSongs(s_songs)
  print('found artists: ', s_artists)
  print('found songs: ', s_songs)
  print('getting recs')
  recs = spot.get_recommendations(seed_genres=s_genres, seed_artists=s_artists, 
    seed_tracks=s_songs, attributes=s_attrs)
  if not recs:
    print('no recs found')
    return ERROR_CODES.ERROR_NO_SPOTIFY_RECS, None
  track_uris = spot.tracksForRecs(recs)
  print('track uris')
  playlist_id, playlist_url = spot.get_playlist_info(pname=pname)
  if playlist_id is None:
    print('playlist id is none')
    return ERROR_CODES.ERROR_NO_PLAYLIST_CREATE, None
  spot.playlist_write_tracks(playlist_id, track_uris)
  print('wrote tracks')
  print('url: ', playlist_url)
  return ERROR_CODES.NO_ERROR, playlist_url


query = 'sensual playlist for two lovers who low key hate each other and ready to break up'


# -*- coding: utf-8 -*-
# modified by Venom for Fenomscrapers (updated 11-19-2020)

'''
    Fenomscrapers Project
'''

import json
import re
try:
	from urlparse import parse_qs, urljoin
	from urllib import urlencode, quote, unquote_plus
except ImportError:
	from urllib.parse import parse_qs, urljoin
	from urllib.parse import urlencode, quote, unquote_plus


from fenomscrapers.modules import cache
from fenomscrapers.modules import client
from fenomscrapers.modules import source_utils
from fenomscrapers.modules import workers


class source:
	def __init__(self):
		self.priority = 2
		self.language = ['en']
		self.base_link = 'https://apibay.org'
		self.search_link = '/q.php?q=%s&cat=0'
		self.min_seeders = 0
		self.pack_capable = True


	def movie(self, imdb, title, aliases, year):
		try:
			url = {'imdb': imdb, 'title': title, 'aliases': aliases, 'year': year}
			url = urlencode(url)
			return url
		except:
			return


	def tvshow(self, imdb, tvdb, tvshowtitle, aliases, year):
		try:
			url = {'imdb': imdb, 'tvdb': tvdb, 'tvshowtitle': tvshowtitle, 'aliases': aliases, 'year': year}
			url = urlencode(url)
			return url
		except:
			return


	def episode(self, url, imdb, tvdb, title, premiered, season, episode):
		try:
			if not url: return
			url = parse_qs(url)
			url = dict([(i, url[i][0]) if url[i] else (i, '') for i in url])
			url['title'], url['premiered'], url['season'], url['episode'] = title, premiered, season, episode
			url = urlencode(url)
			return url
		except:
			return


	def sources(self, url, hostDict):
		sources = []
		if not url: return sources
		try:
			data = parse_qs(url)
			data = dict([(i, data[i][0]) if data[i] else (i, '') for i in data])

			title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
			title = title.replace('&', 'and').replace('Special Victims Unit', 'SVU')
			aliases = data['aliases']
			hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode'])) if 'tvshowtitle' in data else data['year']
			episode_title = data['title'] if 'tvshowtitle' in data else None

			query = '%s %s' % (title, hdlr)
			query = re.sub('[^A-Za-z0-9\s\.-]+', '', query)

			url = self.search_link % quote(query)
			url = urljoin(self.base_link, url)
			# log_utils.log('url = %s' % url, log_utils.LOGDEBUG)

			rjson = client.request(url, error=True)
			if not rjson or any(value in rjson for value in ['521 Origin Down', 'No results returned', 'Connection Time-out']):
				return sources
			files = json.loads(rjson)
			for file in files:
				try:
					hash = file['info_hash']
					name = file['name']
					name = source_utils.clean_name(title, name)
					if source_utils.remove_lang(name, episode_title):
						continue
					url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name) 

					if not source_utils.check_title(title, aliases, name, hdlr, data['year']):
						continue

					if episode_title: # filter for episode multi packs (ex. S01E01-E17 is also returned in query)
						if not source_utils.filter_single_episodes(hdlr, name):
							continue
					elif not episode_title: #filter for eps returned in movie query (rare but movie and show exists for Run in 2020)
						ep_strings = [r'(?:\.|\-)s\d{2}e\d{2}(?:\.|\-|$)', r'(?:\.|\-)s\d{2}(?:\.|\-|$)', r'(?:\.|\-)season(?:\.|\-)\d{1,2}(?:\.|\-|$)']
						if any(re.search(item, name.lower()) for item in ep_strings):
							continue

					try:
						seeders= file['seeders']
						if self.min_seeders > seeders:
							continue
					except:
						seeders = 0
						pass

					quality, info = source_utils.get_release_quality(name, url)
					try:
						dsize, isize = source_utils.convert_size(float(file["size"]), to='GB')
						info.insert(0, isize)
					except:
						dsize = 0
						pass
					info = ' | '.join(info)

					sources.append({'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'quality': quality,
												'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize})
				except:
					source_utils.scraper_error('PIRATEBAY')
					continue
			return sources
		except:
			source_utils.scraper_error('PIRATEBAY')
			return sources


	def sources_packs(self, url, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		self.sources = []
		if not url: return self.sources
		try:
			self.search_series = search_series
			self.total_seasons = total_seasons
			self.bypass_filter = bypass_filter

			data = parse_qs(url)
			data = dict([(i, data[i][0]) if data[i] else (i, '') for i in data])

			self.title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU')
			self.aliases = data['aliases']
			self.imdb = data['imdb']
			self.year = data['year']
			self.season_x = data['season']
			self.season_xx = self.season_x.zfill(2)

			query = re.sub('[^A-Za-z0-9\s\.-]+', '', self.title)
			queries = [
						self.search_link % quote(query + ' S%s' % self.season_xx),
						self.search_link % quote(query + ' Season %s' % self.season_x)
							]
			if search_series:
				queries = [
						self.search_link % quote(query + ' Season'),
						self.search_link % quote(query + ' Complete')
								]

			threads = []
			for url in queries:
				link = urljoin(self.base_link, url)
				threads.append(workers.Thread(self.get_sources_packs, link))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('PIRATEBAY')
			return self.sources


	def get_sources_packs(self, link):
		try:
			# log_utils.log('link = %s' % str(link), __name__, log_utils.LOGDEBUG)
			rjson = client.request(link, error=True)
			if not rjson or any(value in rjson for value in ['521 Origin Down', 'No results returned', 'Connection Time-out']):
				return
			files = json.loads(rjson)
		except:
			source_utils.scraper_error('PIRATEBAY')
			return

		for file in files:
			try:
				hash = file['info_hash']
				name = file['name']
				name = source_utils.clean_name(self.title, name)
				if source_utils.remove_lang(name):
					continue
				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name) 

				if not self.search_series:
					if not self.bypass_filter:
						if not source_utils.filter_season_pack(self.title, self.aliases, self.year, self.season_x, name):
							continue
					package = 'season'

				elif self.search_series:
					if not self.bypass_filter:
						valid, last_season = source_utils.filter_show_pack(self.title, self.aliases, self.imdb, self.year, self.season_x, name, self.total_seasons)
						if not valid:
							continue
					else:
						last_season = self.total_seasons
					package = 'show'

				try:
					seeders= file['seeders']
					if self.min_seeders > seeders:
						continue
				except:
					seeders = 0
					pass

				quality, info = source_utils.get_release_quality(name, url)
				try:
					dsize, isize = source_utils.convert_size(float(file["size"]), to='GB')
					info.insert(0, isize)
				except:
					dsize = 0
					pass
				info = ' | '.join(info)

				item = {'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'quality': quality,
							'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize, 'package': package}
				if self.search_series:
					item.update({'last_season': last_season})
				self.sources.append(item)
			except:
				source_utils.scraper_error('PIRATEBAY')
				continue


	def resolve(self, url):
		return url
# -*- coding: utf-8 -*-
# created by Venom for Fenomscrapers (updated 11-14-2021)
"""
	Fenomscrapers Project
"""

import re
from urllib.parse import quote_plus, unquote_plus
from fenomscrapers.modules import client
from fenomscrapers.modules import source_utils
from fenomscrapers.modules import workers


class source:
	def __init__(self):
		self.priority = 3
		self.language = ['en']
		self.domains = ['torrentdownload.info']
		self.base_link = 'https://www.torrentdownload.info'
		self.search_link = '/search?q=%s'
		self.min_seeders = 1
		self.pack_capable = True
		self.movie = True
		self.tvshow = True

	def sources(self, data, hostDict):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			self.title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
			self.title = self.title.replace('&', 'and').replace('Special Victims Unit', 'SVU')
			self.aliases = data['aliases']
			self.episode_title = data['title'] if 'tvshowtitle' in data else None
			self.year = data['year']
			self.hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode'])) if 'tvshowtitle' in data else self.year

			query = '%s %s' % (self.title, self.hdlr)
			query = re.sub(r'[^A-Za-z0-9\s\.-]+', '', query)
			urls = []
			url = self.search_link % quote_plus(query)
			url = '%s%s' % (self.base_link, url)
			urls.append(url)
			urls.append(url + '&p=2')
			# log_utils.log('urls = %s' % urls)
			threads = []
			append = threads.append
			for url in urls:
				append(workers.Thread(self.get_sources, url))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('TORRENTDOWNLOAD')
			return self.sources

	def get_sources(self, url):
		try:
			r = client.request(url, timeout='5')
			if not r: return
			r = re.sub(r'\n', '', r)
			r = re.sub(r'\t', '', r)
			posts = re.compile(r'<table\s*class\s*=\s*["\']table2["\']\s*cellspacing\s*=\s*["\']\d+["\']>(.*?)</table>', re.I).findall(r)
			posts = client.parseDOM(posts, 'tr')
		except:
			source_utils.scraper_error('TORRENTDOWNLOAD')
			return
		for post in posts:
			try:
				if '<th' in post: continue
				links = re.compile(r'<a\s*href\s*=\s*["\'](.+?)["\']>.*?<td class\s*=\s*["\']tdnormal["\']>((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))</td><td class\s*=\s*["\']tdseed["\']>([0-9]+|[0-9]+,[0-9]+)</td>', re.I).findall(post)
				for items in links:
					link = items[0].split("/")
					hash = link[1].lower()
					name = link[2].replace('+MB+', '')
					name = unquote_plus(name).replace('&amp;', '&')
					name = source_utils.clean_name(name)

					if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue
					name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
					if source_utils.remove_lang(name_info): continue

					url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)

					if not self.episode_title: #filter for eps returned in movie query (rare but movie and show exists for Run in 2020)
						ep_strings = [r'[.-]s\d{2}e\d{2}([.-]?)', r'[.-]s\d{2}([.-]?)', r'[.-]season[.-]?\d{1,2}[.-]?']
						if any(re.search(item, name.lower()) for item in ep_strings): continue
					try:
						seeders = int(items[2].replace(',', ''))
						if self.min_seeders > seeders: continue
					except: seeders = 0

					quality, info = source_utils.get_release_quality(name_info, url)
					try:
						size = re.search(r'((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))', items[1]).group(0)
						dsize, isize = source_utils._size(size)
						info.insert(0, isize)
					except: dsize = 0
					info = ' | '.join(info)

					self.sources_append({'provider': 'torrentdownload', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info,
														'quality': quality, 'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize})
			except:
				source_utils.scraper_error('TORRENTDOWNLOAD')

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			self.search_series = search_series
			self.total_seasons = total_seasons
			self.bypass_filter = bypass_filter

			self.title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU')
			self.aliases = data['aliases']
			self.imdb = data['imdb']
			self.year = data['year']
			self.season_x = data['season']
			self.season_xx = self.season_x.zfill(2)

			query = re.sub(r'[^A-Za-z0-9\s\.-]+', '', self.title)
			queries = [
						self.search_link % quote_plus(query + ' S%s' % self.season_xx),
						self.search_link % quote_plus(query + ' Season %s' % self.season_x)]
			if search_series:
				queries = [
						self.search_link % quote_plus(query + ' Season'),
						self.search_link % quote_plus(query + ' Complete')]
			threads = []
			append = threads.append
			for url in queries:
				link = '%s%s' % (self.base_link, url)
				append(workers.Thread(self.get_sources_packs, link))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources
		except:
			source_utils.scraper_error('TORRENTDOWNLOAD')
			return self.sources

	def get_sources_packs(self, link):
		# log_utils.log('link = %s' % str(link))
		try:
			r = client.request(link, timeout='5')
			if not r: return
			r = re.sub(r'\n', '', r)
			r = re.sub(r'\t', '', r)
			posts = re.compile(r'<table\s*class\s*=\s*["\']table2["\']\s*cellspacing\s*=\s*["\']\d+["\']>(.*?)</table>', re.I).findall(r)
			posts = client.parseDOM(posts, 'tr')
		except:
			source_utils.scraper_error('TORRENTDOWNLOAD')
			return
		for post in posts:
			try:
				if '<th' in post: continue
				links = re.compile(r'<a\s*href\s*=\s*["\'](.+?)["\']>.*?<td class\s*=\s*["\']tdnormal["\']>((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))</td><td class\s*=\s*["\']tdseed["\']>([0-9]+|[0-9]+,[0-9]+)</td>', re.I).findall(post)
				for items in links:
					link = items[0].split("/")
					hash = link[1].lower()
					name = link[2].replace('+MB+', '')
					name = unquote_plus(name).replace('&amp;', '&')
					name = source_utils.clean_name(name)

					if not self.search_series:
						if not self.bypass_filter:
							if not source_utils.filter_season_pack(self.title, self.aliases, self.year, self.season_x, name):
								continue
						package = 'season'

					elif self.search_series:
						if not self.bypass_filter:
							valid, last_season = source_utils.filter_show_pack(self.title, self.aliases, self.imdb, self.year, self.season_x, name, self.total_seasons)
							if not valid: continue
						else:
							last_season = self.total_seasons
						package = 'show'

					name_info = source_utils.info_from_name(name, self.title, self.year, season=self.season_x, pack=package)
					if source_utils.remove_lang(name_info): continue

					url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
					try:
						seeders = int(items[2].replace(',', ''))
						if self.min_seeders > seeders: continue
					except: seeders = 0

					quality, info = source_utils.get_release_quality(name_info, url)
					try:
						size = re.search(r'((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))', items[1]).group(0)
						dsize, isize = source_utils._size(size)
						info.insert(0, isize)
					except: dsize = 0
					info = ' | '.join(info)

					item = {'provider': 'torrentdownload', 'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'name_info': name_info, 'quality': quality,
								'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize, 'package': package}
					if self.search_series: item.update({'last_season': last_season})
					self.sources_append(item)
			except:
				source_utils.scraper_error('TORRENTDOWNLOAD')

	def resolve(self, url):
		return url
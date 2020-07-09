from river_mwclient.esports_client import EsportsClient
from river_mwclient.auth_credentials import AuthCredentials
from toornament_scraper.parser import Parser
from toornament_scraper.match import Match
import mwparserfromhell
from mwparserfromhell.nodes import Template


class MenaScraper(object):
	def __init__(self, site: EsportsClient, title: str):
		self.site = site
		self.event = self.site.target(title).strip()
		self.data_page = self.site.client.pages['Data:' + self.event]
		self.overview_page = self.site.client.pages[self.event]
		self.toornament = self.site.cargo_client.query_one_result(
			tables='Tournaments',
			where='OverviewPage="{}"'.format(self.event),
			fields='ScrapeLink'
		)
		self.summary = "Edit made by web scraping!"
		self.parser = Parser()
		
	def run(self):
		# TODO: parser should return a list of matches
		matches = self.parser.run(self.toornament)
		text = self.data_page.text()
		wikitext = mwparserfromhell.parse(text)
		i = 0
		for template in wikitext.filter_templates():
			template: Template
			if template.name.matches('MatchSchedule'):
				if i >= len(matches):
					break
				match = matches[i]
				match: Match
				team1 = template.get('team1').value.strip()
				team2 = template.get('team2').value.strip()
				# TODO: some team validation? however remember there can be disambiguation
				# TODO: so parse out anything in () when doing validation
				if match.completed:
					template.add('team1score', str(match.team1score))
					template.add('team2score', str(match.team2score))
					template.add('winner', str(match.winner))
					
					# TODO: remove these teams from being saved, this is temporary while debugging
					template.add('team1', match.team1)
					template.add('team2', match.team2)
					# TODO: handle ff?
				i += 1
		self.data_page.save(str(wikitext), summary=self.summary)


if __name__ == "__main__":
	credentials = AuthCredentials(user_file='me')
	site = EsportsClient('lol', credentials=credentials)  # Set wiki
	scraper = MenaScraper(site, 'Intel Arabian Cup 2020/Egypt/Split 1')
	scraper.run()
	# TODO: some test here

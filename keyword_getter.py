import re
import os
import time
import csv
import json
import requests
from fake_useragent import UserAgent

base_url = "http://ec2-13-126-117-106.ap-south-1.compute.amazonaws.com:8000/"

class GetGoogleSearchKeywords:
    def __init__(self):
        """ global variables """
        self.queue = set()
        self.already_fetched = set()
        self.country = "US"
        self.language = "en"
        self.threshold_count = 50000
        self.api_rate_limit = 0
        self.keywords_count = 0
        self.results = []

    def checkSeedKeywordExists(self, keyword, meta_keyword):
        """ 
        This function checks whether suggestions has meta keywords in it
        """
        keyword_ = re.sub('[^A-Za-z0-9]+', '', keyword)
        if meta_keyword.lower() in keyword.lower() or meta_keyword.lower() in keyword_.lower():
            return True
        else:
            return False

    def fetchSuggestion(self, keyword, seed_keyword, meta_keyword):
        """ return list of suggestion based on the geolocation and language for a seed keyword """
        url = "http://suggestqueries.google.com/complete/search?client=chrome&hl={}&gl={}&callback=?&q={}".format(
            self.language, self.country, keyword)
        ua = UserAgent(use_cache_server=False, verify_ssl=False)
        headers = {"user-agent": ua.chrome, "dataType": "jsonp"}

        response = requests.get(url, headers=headers, verify=True)
        suggestions = json.loads(response.text)

        sugg = []
        index = 0
        relevancies = []
        if "google:suggestrelevance" in suggestions[4].keys():
            relevancies = suggestions[4]['google:suggestrelevance']
        for word in suggestions[1]:
            if self.checkSeedKeywordExists(word, meta_keyword):
                sugg.append({
                    'keyword': word,
                    'relevancy_score': relevancies[index] if len(relevancies) > 0 else None,
                    'seed_keyword': seed_keyword,
                    'meta_keyword': meta_keyword,
                })
            else:
                continue
            index += 1

        return sugg

    def fetchRelatedkeywords(self, keyword, meta_keyword):
        """ fetches all the suggestions when an array of strings formed by seed keyword concatenated with characters a to z  """
        suffix = ["", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l",
                  "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w" "x", "y", "z"]
        suffix_arr = list(map(lambda x: keyword+" "+x, suffix))
        duplicates = set()
        for word in suffix_arr:
            suggestion = self.fetchSuggestion(word, keyword, meta_keyword)
            self.api_rate_limit+=1
            for query in suggestion:
                if query['keyword'] not in duplicates:
                    duplicates.add(query['keyword'])
                    self.results.append(query)
                    if query['keyword'] not in self.already_fetched:
                        self.queue.add(query['keyword'])   
        self.keywords_count += len(self.results)


def getSeedKeywords(fetching_status):
    """ This function makes an api call to fetch keywords which are not fetched yet  """
    username = ""
    if fetching_status == 1:
        username = os.getlogin()
    res = requests.get(
        '{}seedkeywords/list/?keyword_fetching_status={}&username={}'.format(base_url, fetching_status,username))
    json_res = res.json()
    return json_res


def updatestatus(id, status):
    """ This function changes the status of a seed keyword """
    username = os.getlogin()
    res = requests.put('{}update/{}/'.format(base_url, id),
                       data={"keyword_fetching_status": status, "user_fetched": username})
    res = res.json()
    return res


def uploadcsvfile(csv_filename):
    """ uploads the output csv file to server """
    files = {'csvfile': open(csv_filename, 'rb')}
    res = requests.post("{}upload/csvfile/".format(base_url), files=files)
    return res.status_code

def doesJsonFileExists(json_filename):
    return os.path.exists(json_filename)

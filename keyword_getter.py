import re
import os
import time
import csv
import json
import boto3 
import requests
from fake_useragent import UserAgent

base_url = "http://ec2-13-126-117-106.ap-south-1.compute.amazonaws.com:8000/"
# base_url = "http://127.0.0.1:8000/"

class GetGoogleSearchKeywords:
    def __init__(self):
        """ global variables """
        self.queue = set()
        self.already_fetched = set()
        self.country = "US"
        self.language = "en"
        self.threshold_count = 200
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

def uploadFileToS3(filepath,filename):
    # fetches s3 credentials from an api
    res = requests.get('{}s3/credentials/'.format(base_url))
    json_res = res.json()
    # credentials assigned
    REGION = json_res['REGION'] 
    ACCESS_KEY_ID = json_res['ACCESS_KEY_ID']
    SECRET_ACCESS_KEY = json_res['SECRET_ACCESS_KEY']
    PATH_IN_COMPUTER = filepath 
    BUCKET_NAME = json_res['BUCKET_NAME'] 
    KEY = '{}{}'.format(json_res['KEY'],filename) # file path in S3 
    s3_resource = boto3.resource(
        's3', 
        region_name = REGION, 
        aws_access_key_id = ACCESS_KEY_ID,
        aws_secret_access_key = SECRET_ACCESS_KEY
    ) 
    s3_resource.Bucket(BUCKET_NAME).put_object(
        Key = KEY, 
        Body = open(PATH_IN_COMPUTER, 'rb')
    )
    return
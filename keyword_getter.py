import re
import os
import time
import csv
import json
import boto3 # helps in accessing aws s3
import random 
import requests

# api base url from which we are fetching seed keywords
base_url = "http://ec2-13-126-117-106.ap-south-1.compute.amazonaws.com:8000/"

class GetGoogleSearchKeywords:
    """ 
    input : seed keyword
    output : list of suggestions for a seed keyword
    """
    def __init__(self):
        """ global variables """
        self.queue = set() # list of seed keywords for which suggestions needs to be fetched
        self.already_fetched = set() # list of seed keywords for which suggestions has been fetched
        self.country = "US" # defining from which country we need to fetch suggestions from
        self.language = "en" # defining language of a suggestion
        self.threshold_count = 50000 # this variables helps in writing keywords data into a new file if keywords count in existing csv file crossed threshold count
        self.api_rate_limit = 0 # counts no of api calls has been made and if api calls crosses 750 we put process to sleep for 60sec
        self.keywords_count = 0 # counts no of keywords has been fetched for a seed keyword so that we can compare with threshold count and we can write data into new csv file
        self.results = [] # parameter which stores suggestions which we write into csv file

    def checkSeedKeywordExists(self, keyword, meta_keyword):
        """ 
        This function checks whether suggestions has seed keywords.
        """
        keyword_ = re.sub('[^A-Za-z0-9]+', '', keyword)
        split_meta_keyword =  meta_keyword.split()
        condition = False
        """ 
        splitting meta keyword with space and checking each word from meta keyword exists in the keyword
        example :: for keyword "air bbq fryer" and meta keyword "air fryer" we split meta keyword
        whch is ["air","fryer"] and we check each value in the array exists in the keyword "air bbq fryer"
        """
        if len(split_meta_keyword) > 1:
            condition = all(x.lower() in keyword.lower() for x in split_meta_keyword)

        if meta_keyword.lower() in keyword.lower() or meta_keyword.lower() in keyword_.lower() or condition:
            return True
        else:
            return False

    def fetchSuggestion(self, keyword, seed_keyword, meta_keyword):
        """ return list of suggestion based on the geolocation and language for a seed keyword """
        # user agent is an HTTP browser request header that gives servers information regarding the client device and/or operating system on which the browser is running
        user_agent_list = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        ]
        url = "http://suggestqueries.google.com/complete/search?client=chrome&hl={}&gl={}&callback=?&q={}".format(
            self.language, self.country, keyword)
        user_agent = random.choice(user_agent_list)
        headers = {"user-agent": user_agent, "dataType": "jsonp"}
        response = requests.get(url, headers=headers, verify=True)
        if response.status_code == 200:
            suggestions = json.loads(response.text)
            sugg = []
            index = 0
            relevancies = []
            suggesttypes = []
            suggestsubtypes = []
            verbatimrelevance = ""
            if "google:suggestrelevance" in suggestions[4].keys():
                relevancies = suggestions[4]['google:suggestrelevance']
            if "google:suggesttype" in suggestions[4].keys():
                suggesttypes = suggestions[4]['google:suggesttype']
            if "google:verbatimrelevance" in suggestions[4].keys():
                verbatimrelevance = suggestions[4]['google:verbatimrelevance']
            if "google:suggestsubtypes" in suggestions[4].keys():
                suggestsubtypes = suggestions[4]['google:suggestsubtypes']
            for word in suggestions[1]:
                if self.checkSeedKeywordExists(word, meta_keyword):
                    sugg.append({
                        'keyword': word,
                        'relevancy_score': relevancies[index] if len(relevancies) > 0 else None,
                        'suggesttype':suggesttypes[index] if len(suggesttypes) > 0 else None,
                        'verbatimrelevance' : verbatimrelevance,
                        'seed_keyword': seed_keyword,
                        'meta_keyword': meta_keyword,
                        'suggestsubtype' : suggestsubtypes[index] if len(suggestsubtypes) > 0 else None,
                    })
                else:
                    continue
                index += 1
            return sugg
        # returning false when google blocks an ip for some time 
        return False

    def fetchRelatedkeywords(self, keyword, meta_keyword):
        """ fetches all the suggestions when an array of strings formed by seed keyword concatenated with characters a to z  """
        prefix = ["how", "which", "why", "where", "who", "when", "are", "what"]
        suffix = ["", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l",
                  "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w" "x", "y", "z"]
        suffix_arr = list(map(lambda x: keyword+" "+x, suffix))
        prefix_arr = list(map(lambda x: x+" "+keyword, prefix))
        suffix_arr.extend(prefix_arr)
        # removes duplicates for a seed keyword
        duplicates = set()
        for word in suffix_arr:
            suggestion = self.fetchSuggestion(word, keyword, meta_keyword)
            if suggestion == False:
                return False
            self.api_rate_limit+=1
            for query in suggestion:
                if query['keyword'] not in duplicates:
                    duplicates.add(query['keyword'])
                    # allows same keywords with multiple keywords
                    # self.results.append(query)
                    if query['keyword'] not in self.already_fetched:
                        # does not allow same keyword with multiple keywords
                        # this line is temporary need to remove after fetching 10 categories
                        self.results.append(query)
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
    """ checks json file exists in a path  """
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
    uploadcsvfile(filepath)
    return

def addLog(log_info,seed_keyword="",meta_keyword=""):
    """ adding logs to the databse """
    payload = {
        "user" : os.getlogin(),
        "seed_keyword":seed_keyword,
        "meta_keyword":meta_keyword,
        "log_info":log_info
    }
    res = requests.post('{}add/issue/'.format(base_url),data=payload)
    return res.status_code
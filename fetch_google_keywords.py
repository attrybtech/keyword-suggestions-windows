import os
import sys
import time
from tkinter import *
import tkinter.messagebox
from threading import *
from keyword_getter import *
from tkinter import ttk
import tkinter.font as fnt

# defining tkinter window
top = Tk()
top.title('Keyword Tool')
top.geometry('500x500') # Size 200, 200

# defining progress bar widget
progressbar = ttk.Progressbar(top, orient = HORIZONTAL,length = 400, mode = 'indeterminate',value=5)

def getSearchKeywords():
    # defining GetGoogleSearchKeywords class instance from keyword_getter.py file
    keyword_getter = GetGoogleSearchKeywords()
    # exception handling(which covers all issues i.e., api's not working due to server issue,internet issue,issue with exe dependencies)
    try:
        # fetches seed keywords from database(looks for pending seed keywords of a particular user first and then goes for keywords whose related keywords has not been fetched yet)
        while(stop == 0 and (len(getSeedKeywords(1)) > 0 or len(getSeedKeywords(0)))):
            seedkeywords = getSeedKeywords(1) if len(getSeedKeywords(1)) > 0 else getSeedKeywords(0)
            # writes  keywords data into file
            s_keyword = seedkeywords[0]
            meta_keyword = s_keyword['keyword']
            # defining output file path
            if getattr(sys, 'frozen', False):
                application_path = os.path.dirname(sys.executable)
            elif __file__:
                application_path = os.path.dirname(__file__)

            csv_filename = "{}_keywords.csv".format(meta_keyword)
            csv_filepath = os.path.join(application_path,csv_filename)
            #  maintains queue,already_fetched keywords
            json_filename = '{}_queue.json'.format(meta_keyword)
            json_filepath = os.path.join(application_path,json_filename)
            # for pending processes checks json file exists in repo to continue the process
            if not doesJsonFileExists(json_filepath) and s_keyword["keyword_fetching_status"] ==  1:
                updatestatus(s_keyword['id'], 0)
                continue
            # used for file naming
            index = 1
            # distinguishes not started and pending seed keywords
            if s_keyword['keyword_fetching_status'] == 1:
                jsonfile = open(json_filepath, "r")
                queue = json.loads(jsonfile.read())
                keyword_getter.queue = set(queue["queued_keywords"])
                keyword_getter.already_fetched = set(queue['already_fetched_keywords'])
                keyword_getter.keywords_count = queue['fetched_keywords_count']
                csv_filepath = queue["csv_filepath"]
                csv_filename = queue["csv_filename"]
                index = queue["index"]
            else:
                keyword_getter.queue.add(meta_keyword)
                # creates a csv file for new seed keyword
                ofile = open(csv_filepath, 'w+',encoding="utf-8", newline="")
                writer = csv.DictWriter(ofile, fieldnames=[
                    "keyword", "relevancy_score", "seed_keyword", "meta_keyword"])
                writer.writeheader()
                ofile.close()
            while(stop==0 and len(keyword_getter.queue) > 0):
                ofile = open(csv_filepath, 'a',encoding="utf-8", newline="")
                writer = csv.DictWriter(ofile, fieldnames=[
                    "keyword", "relevancy_score", "seed_keyword", "meta_keyword"])
                seed_keyword = keyword_getter.queue.pop()
                keyword_getter.already_fetched.add(seed_keyword)
                related_keywords = keyword_getter.fetchRelatedkeywords(seed_keyword, meta_keyword)
                # case when google blocks your ip for few minutes
                if related_keywords == False:
                    # adds log to db table
                    addLog("HTTP 403 Forbidden",seed_keyword,meta_keyword)
                    keyword_getter.queue.add(seed_keyword)
                    keyword_getter.already_fetched.remove(seed_keyword)
                    keyword_getter.results = []
                    time.sleep(60)
                    continue
                queue_backup = {
                    "queued_keywords": list(keyword_getter.queue),
                    "already_fetched_keywords" : list(keyword_getter.already_fetched),
                    "csv_filepath": csv_filepath,
                    "csv_filename" : csv_filename,
                    "fetched_keywords_count" : keyword_getter.keywords_count,
                    "index" : index
                }
                # writes queue into jsonfile so that when a user restarts process continuous from where it ended
                with open(json_filepath, 'w', encoding='utf-8') as f:
                    json.dump(queue_backup, f, ensure_ascii=False, indent=4)

                # updates seed keyword fetching status to 1(pending) for the keywords which has not been fetched yet
                if s_keyword['keyword_fetching_status'] == 0:
                    updatestatus(s_keyword['id'], 1)
                    s_keyword['keyword_fetching_status'] == 1
                # writing data into the csv file
                writer.writerows(keyword_getter.results)
                ofile.close()
                # conditon which checks api rate limit exceeds 750 so that we can suspend the process for few seconds
                if keyword_getter.api_rate_limit >= 750 :
                    keyword_getter.api_rate_limit = 0
                    time.sleep(15)
                # condition which helps in writing data into new csv files after crossing threshold count
                if keyword_getter.keywords_count > keyword_getter.threshold_count:
                    # uploads a csv file to the server
                    # uploadcsvfile(csv_filepath)
                    uploadFileToS3(csv_filepath,csv_filename)
                    if index == 1:
                        csv_filename = csv_filename.split(".")[0]+"_"+str(index)+".csv"
                    else:
                        csv_filename = csv_filename.split(".")[0].rsplit("_", 1)[
                            0]+"_"+str(index)+".csv"
                    csv_filepath = os.path.join(application_path,csv_filename)
                    ofile = open(csv_filename, 'w+',encoding="utf-8", newline="")
                    writer = csv.DictWriter(ofile, fieldnames=[
                        "keyword", "relevancy_score", "seed_keyword", "meta_keyword"])
                    writer.writeheader()
                    ofile.close()
                    index += 1
                    keyword_getter.keywords_count = 0
                keyword_getter.results = []
            # definin 
            keyword_getter.queue = set()
            keyword_getter.already_fetched = set()
            keyword_getter.keywords_count = 0
            # this condition is added to change status of a keyword for which all the related keywords has been fetched
            if stop == 0:
                # updates seed keyword fetching status to 2 which is Completed
                if s_keyword['keyword_fetching_status'] == 1:
                    updatestatus(s_keyword['id'], 2)
                    uploadFileToS3(csv_filepath,csv_filename)        
    except Exception as e:
        error = str(e)
        # function which add logs to the database
        addLog(error,seed_keyword,meta_keyword)
        # time.sleep(2)
        top.destroy()
        sys.exit()
""" 
Used threading module to run processes asynchronously . In our case we can start,stop and restart the process . without threading we cannot stop the process untill started has been completed 
""" 
def threading():
    # Call getSearchKeywords function
    """ starts the keywords extraction process """
    global stop
    stop = 0
    # 
    if startButton['state'] == NORMAL:
        # defining message box on clicking the start button
        MsgBox = tkinter.messagebox.askquestion ('Start Application','Are you sure you want to start the application',icon = 'question')
        if MsgBox == 'yes':
            t1=Thread(target=getSearchKeywords)
            t1.start()
            # activates the progress bar on starting the process
            progressbar.pack(pady=120,padx=20,side=BOTTOM)
            progressbar.start()
            # diabling the start button and enabling the stop button
            startButton['state'] = DISABLED
            stopButton['state'] = NORMAL

        
def stop():
    """ stops the process """
    # stop variables is used start(0) and stop(1) the process
    global stop 
    MsgBox = tkinter.messagebox.askquestion ('Exit Application','Are you sure you want to exit the application',icon = 'warning')
    if MsgBox == 'yes':
       stop = 1
       startButton['state'] = NORMAL
       stopButton['state'] = DISABLED
       progressbar.pack_forget()


# tkinter frame is an container(rectangular areas of the screens) which can be used to organize the widgets(buttons,progress bar etc....)
app = Frame(top)
app.place(anchor="c", relx=.50, rely=.50)

# defining and organising start and stop button in the frame 
startButton = Button(app, height=2, width=20, text ="Start", command = threading,font = fnt.Font(size = 12))
stopButton = Button(app, height=2, width=20, text ="Stop", command = stop,font = fnt.Font(size = 12))

stopButton['state'] = DISABLED
startButton.grid(pady=10, padx=10)
stopButton.grid(pady=(0,10), padx=10)
app.mainloop()
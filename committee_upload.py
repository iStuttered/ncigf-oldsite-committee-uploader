import requests, urllib3, os, dateutil, time, string, logging, time, json, re, credentials, debugging
from atlassian import Confluence
from os import listdir
from os.path import isfile, join, isdir, exists
from datetime import datetime

api = credentials.generateSession()
logger = debugging.generateLogger()

def isAgenda(file_name) -> bool:
    return "agenda" in file_name.lower()

def isMinutes(file_name:str) -> bool:
    return "minutes" in file_name.lower()

def getAgendasFromFolder(folder_path:str) -> list:

    folder_name = folder_path.split("/")[-1]

    if not os.path.exists(folder_path):
        logger.critical("No folder exists with the name " + folder_name)
        return None
    if not os.path.isdir(folder_path):
        logger.critical(folder_name + " is not a directory.")
        return None

    agendas = [file for file in os.listdir(folder_path) if isAgenda(file)]
    
    return agendas

def getMinutesFromFolder(folder_path:str) -> list:

    folder_name = folder_path.split("/")[-1]

    if not os.path.exists(folder_path):
        logger.critical("No folder exists with the name " + folder_name)
        return None
    if not os.path.isdir(folder_path):
        logger.critical(folder_name + " is not a directory.")
        return None
    
    minutes = [file for file in os.listdir(folder_path) if isMinutes(file)]
    
    return minutes
    

def getAgenda(lines_of_file:list) -> dict:
    """
    Read the lines of a file and get the information about the agenda.

    {
        "Agenda": agenda,
        "Presenters": presenters,
        "Minutes Date": minute_date,
        "Committee Name": committee_name
    }
    
    Args:
        lines_of_file (list): A list of strings from a file.
    
    Returns:
        dict: A dictionary like above.
    """
    agenda = []
    presenters = []
    minutes_date = None
    agendaSection = False
    presenterSection = False

    committee_name = None
    line_index = 0

    lastTopic = ""

    for line in lines_of_file:

        lower = line.lower().strip()

        if "outcome" in lower:
            agendaSection = True
            continue

        if presenterSection and not agendaSection and len(lower) < 1:
            agendaSection = True
            presenterSection = False

        if "presenter" in lower or "leader" in lower:
            agendaSection = False
            presenterSection = True
            continue
        
        if "desired outcome" in lower:
            presenterSection = False
            continue

        if len(lower) < 1:
            continue

        if line_index == 1:
            committee_name = line.strip().replace("Meeting of the ", "")
        
        if line_index < 5:
            search_for_date = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s\d+,\s\d{4}", line)
            if not(search_for_date == None):
                if len(search_for_date.groups()) > 0:
                    matched_date_str = search_for_date.group(0)
                    matched_date = datetime.strptime(matched_date_str, "%B %d, %Y")
                    minutes_date = matched_date.strftime("%m/%d/%y")


        if presenterSection:
            if len(line.strip()) > 0 and not(re.match(r"(D|I|V)[^(a-z)]", line)):
                presenters.append(line.strip())
                
        if agendaSection:
            if lastTopic == None and re.match(r"(\d\d|\d).\s.+", line.strip()):
                lastTopic = line.replace("\n", " ")
            elif lastTopic != "" and not(re.match(r"(\d\d|\d).\s.+", line.strip())):
                lastTopic += line
            elif lastTopic != "" and re.match(r"(\d\d|\d).\s.+", line.strip()):
                cleanedTopic = lastTopic.replace("\n", " ")
                cleanedTopic = re.sub(r"(\d|\d\d)\.\s", "", cleanedTopic).strip()
                agenda.append(cleanedTopic)
                lastTopic = line
        line_index += 1
            
        if lastTopic != None and re.match(r"(\d\d|\d).\s.+", lastTopic.strip()):
            cleanedTopic = lastTopic.replace("\n", " ")
            cleanedTopic = re.sub(r"(\d|\d\d)\.\s", "", cleanedTopic).strip()
            cleanedTopic = re.sub(r"[D|I|V]*\/*[D|I|V]*\/*[D|I|V]", "", cleanedTopic)
            agenda.append(cleanedTopic.strip())

    minutes_failure = minutes_date == None or len(minutes_date) < 1
    presenters_failure = presenters == None or len(presenters) < 1
    agenda_failure = agenda == None or len(agenda) < 1
    committee_name_failure = committee_name == None or len(committee_name) < 1


    if minutes_failure:
        logger.warning("No date was retrieved for this file.")

    if presenters_failure:
        logger.warning("No presenters were retrieved for this file.")

    if agenda_failure:
        logger.warning("No agenda was retrieved for this file.")
    
    if committee_name_failure:
        logger.warning("No committee name present.")

    if minutes_failure or presenters_failure or agenda_failure or committee_name_failure:
        return None

    return {
        "Agenda": agenda,
        "Presenters": presenters,
        "Minutes Date": minutes_date,
        "Committee Name": committee_name
    }

def getAttendees(lines_in_file:list) -> dict:
    """
    Read the lines of a file to retrieve the attendees information in
    dictionary form below:

    {
        "Members Attending": committeeMembersAttending,
        "Members NOT Attending": committeeMembersNotAttending,
        "Others Attending": othersAttending,
        "Topics": committeeTopics
    }
    
    Args:
        lines_of_file (list): The lines of a file as a list of strings.
    
    Returns:
        dict: A dictionary.
    """
    attending = {
        "committeeMembersAttending" : 0,
        "committeeMembersNotAttending" : 1,
        "othersAttending" : 2,
        "committeeTopics" : 3
    }

    committeeMembersAttending = []
    committeeMembersNotAttending = []
    othersAttending = []
    committeeTopics = []

    currentList = -1
    lastLine = ""

    topic = {
        "Topic":"",
        "Description":""
    }

    for line in lines_in_file:
        if "Committee Member Attendees".lower() in line.lower():
            currentList = attending["committeeMembersAttending"]
            continue
        elif "Committee Members not Attending".lower() in line.lower():
            currentList = attending["committeeMembersNotAttending"]
            continue
        elif "Other Attendees".lower() in line.lower():
            currentList = attending["othersAttending"]
            continue
        elif "Roll Call".lower() in line.lower():
            currentList = attending["committeeTopics"]
        
        if currentList == attending["committeeMembersAttending"]:
            committeeMembersAttending.append(line.strip())
        elif currentList == attending["committeeMembersNotAttending"]:
            committeeMembersNotAttending.append(line.strip())
        elif currentList == attending["othersAttending"]:
            othersAttending.append(line.strip())
        elif currentList == attending["committeeTopics"]:
            if len(lastLine) < 1:

                topic["Description"] = topic["Description"].strip()

                committeeTopics.append(topic)

                topic = {
                    "Topic": line.strip(),
                    "Description": ""
                }

            else:
                topic["Description"] += line.replace("\n", " ")
        lastLine = line.strip()
    
    attending_failure = committeeMembersAttending == None or len(committeeMembersAttending) < 1
    not_attending_failure = committeeMembersNotAttending == None
    others_attending_failure = othersAttending == None
    topics_failure = committeeTopics == None or len(committeeTopics) < 1

    if attending_failure:
        logger.warning("Members attending not retrieved.")
    
    if not_attending_failure:
        logger.warning("Members NOT attending not retrieved.")

    if others_attending_failure:
        logger.warning("Others attending not retrieved.")

    if topics_failure:
        logger.warning("Topics not retrieved.")

    if attending_failure or not_attending_failure or others_attending_failure or topics_failure:
        return None

    return {
        "Members Attending": committeeMembersAttending,
        "Members NOT Attending": committeeMembersNotAttending,
        "Others Attending": othersAttending,
        "Topics": committeeTopics
    }


def buildCommitteeMinutes(topics:list) -> str:
    """
    Get the page block for committee minutes belonging to a minutes page.
    
    Args:
        topics (list): A list of dictionaries in the form

        {
            "Topic" : "A random Topic",
            "Description" : A random Description"
        }
    
    Returns:
        str: A page block for committee minutes belonging to a minutes page.
    """
    beginning = "<ac:structured-macro ac:name=\"content-block\" ac:schema-version=\"1\" ac:macro-id=\"f9b73644-be07-43c6-ae3b-6fcfe601a19a\"><ac:parameter ac:name=\"id\">1856492229</ac:parameter><ac:parameter ac:name=\"class\">minutes-action</ac:parameter><ac:rich-text-body><h1>Minutes</h1>"
        
    table = ""

    for index in range(len(topics)):
        table += "<h2>" + topics[index]["Topic"] + "</h2>"

        paragraphs = topics[index]["Description"].split("\n\n")

        for description in paragraphs:
            table += "<p>" + description + "</p>"

    end = "</ac:rich-text-body></ac:structured-macro>"

    return beginning + table + end

def buildCommitteeAttending(attending:list, notattending:list, otherattending:list) -> str:
    """
    Get the attending members block for a committee minutes page.
    
    Args:
        attending (list): A list of committee members attending a paticular minute
        notattending (list): A list of committee members NOT attending a paticular minute
        otherattending (list): A list of others attending a paticular minute
    
    Returns:
        str: A page block representing the attending members in a minutes page.
    """

    beginning = "<ac:structured-macro ac:name=\"content-block\" ac:schema-version=\"1\" ac:macro-id=\"ea1fb4c5-4895-4807-9985-534d76c03834\"><ac:parameter ac:name=\"not-tabbed\">true</ac:parameter><ac:parameter ac:name=\"id\">1858162090</ac:parameter><ac:parameter ac:name=\"class\">minutes-attending</ac:parameter><ac:rich-text-body><h1>Attending</h1><p><br /></p>"
        
    table = "<table class=\"wrapped\"><colgroup><col style=\"width: 29.0px;\" /></colgroup><tbody><tr><th style=\"text-align: left;\">Members Attending</th></tr>"
        
    for index in range(len(attending)):
        if "\u00e2\u0080\u0093" in attending[index]:
            temp = ", ".join(attending[index].split("\u00e2\u0080\u0093"))
            table += "<tr><td colspan=\"1\">" + temp + "</td></tr>"
        else:
            table += "<tr><td colspan=\"1\">" + attending[index] + "</td></tr>"

    table += "</tbody></table><table class=\"wrapped\"><colgroup><col /></colgroup><tbody><tr><th>Members Not Attending</th></tr>"
        
    for index in range(len(notattending)):
        table += "<tr><td colspan=\"1\">" + notattending[index] + "</td></tr>"
    
    table += "</tbody></table><table class=\"wrapped\"><colgroup><col /></colgroup><tbody><tr><th>Others Attending</th></tr>"
        
    for index in range(len(otherattending)):
        table += "<tr><td colspan=\"1\">" + otherattending[index] + "</td></tr>"
            
    table += "</tbody></table>"

    closing = "</ac:rich-text-body></ac:structured-macro>"

    return beginning + table + closing

def buildCommitteeAgenda(agenda:list) -> str:
    """
    Get the committee agenda page block from a committee page.
    
    Args:
        agenda (list): A list of dictionaries in the form 

        {
            "Topic" : "A random Topic",
            "Agenda": "A random Presenter"
        }
    
    Returns:
        str: A page block of the committee agenda.
    """

    beginning = "<ac:structured-macro ac:name=\"content-block\" ac:schema-version=\"1\" ac:macro-id=\"338bbab4-ea9a-4278-8b52-6c7ec3ae2398\"><ac:parameter ac:name=\"not-tabbed\">true</ac:parameter><ac:parameter ac:name=\"id\">1856481342</ac:parameter><ac:parameter ac:name=\"class\">minutes-agenda</ac:parameter><ac:rich-text-body><h1>Agenda</h1>"
        
    table = "<table class=\"wrapped\"><colgroup><col /><col /></colgroup><tbody><tr><th>Topic</th><th>Presenter</th></tr>"

    for index in range(len(agenda)):
        table += "<tr><td colspan=\"1\">" + " - ".join(str(agenda[index]["Topic"]).split("\u00e2\u20ac\u201c")) + "</td><td colspan=\"1\">" + str(agenda[index]["Presenter"]) + "</td></tr>"
    
    table += "</tbody></table>"

    closing = "</ac:rich-text-body></ac:structured-macro>"

    return beginning + table + closing

def buildCommitteeStatus(committeeName:str, minutes_date:str, committeeStatus:str) -> str:
    """
    Get the status of a paticular committee.
    
    Args:
        committeeName (str): The name of a committee
        minutes_date (str): The date of a particular minutes
    committeeStatus (str): The status of a paticular committee as "Approved"
    "
    
    Returns:
        str: A page block represnting the status of a committee.
    """

    beginning = "<ac:structured-macro ac:name=\"content-block\" ac:schema-version=\"1\" ac:macro-id=\"71c4d118-3da1-4e97-8e1d-f2faf9b45d0f\"><ac:parameter ac:name=\"id\">1856481235</ac:parameter><ac:parameter ac:name=\"class\">minutes-meta</ac:parameter><ac:rich-text-body><ac:structured-macro ac:name=\"details\" ac:schema-version=\"1\" ac:macro-id=\"6561762b-bb94-4120-b624-82bc63b5fd28\"><ac:parameter ac:name=\"id\">minutesandagenda</ac:parameter><ac:rich-text-body>"
        
    table = "<table class=\"wrapped\"><colgroup><col /><col /></colgroup><tbody><tr><th><p>Committee Name</p></th><td><p>"
    table += committeeName + "</p></td></tr><tr><th><p>Date</p></th><td><p>"

    table += minutes_date + "</p></td></tr><tr><th><p>Status</p></th><td><div class=\"content-wrapper\"><ac:structured-macro ac:name=\"minutestatus\" ac:schema-version=\"1\" ac:macro-id=\"1c0ed33a-a4c3-48f4-9a49-4b1a9735e9bf\"><ac:parameter ac:name=\"atlassian-macro-output-type\">INLINE</ac:parameter><ac:rich-text-body><p>"
    table += committeeStatus + "</p></ac:rich-text-body></ac:structured-macro></div></td></tr></tbody></table>"
        
    closing = "</ac:rich-text-body></ac:structured-macro></ac:rich-text-body></ac:structured-macro>"
    
    return beginning + table + closing



def buildMinute(
    committeeName:str,
    committeeminutes_date:str,
    committeeMinutesAttending:list, 
    committeeMinutesNotAttending:list, 
    committeeMinutesOtherAttending:list,
    committeeAgenda:list,
    committeeTopics:list,
    committeeMinutesStatus:str = "Approved") -> str:

    """
    Return a string representation of a ConfluencePage which can be uploaded to
    Confluence.
    """
    
    beginning = "<ac:structured-macro ac:name=\"content-layer\" ac:schema-version=\"1\" ac:macro-id=\"9dec53ff-ddd1-4959-824f-4f1ae61c797a\"><ac:parameter ac:name=\"id\">1856481233</ac:parameter><ac:rich-text-body><ac:structured-macro ac:name=\"content-column\" ac:schema-version=\"1\" ac:macro-id=\"2c808257-9edf-40b1-a12d-466b68e25950\"><ac:parameter ac:name=\"id\">1856481236</ac:parameter><ac:rich-text-body>"
        
    content = str(buildCommitteeStatus(committeeName, committeeminutes_date, committeeMinutesStatus))
    content += str(buildCommitteeAgenda(committeeAgenda))
    content += str(buildCommitteeAttending(committeeMinutesAttending, committeeMinutesNotAttending, committeeMinutesOtherAttending))
    content += str(buildCommitteeMinutes(committeeTopics))

    closing = "</ac:rich-text-body></ac:structured-macro></ac:rich-text-body></ac:structured-macro>"
    
    return beginning + content + closing

def padMonthOrDay(dateValue:int) -> str:
    """
    Add a zero before a single digit section of date.
    
    Args:
        dateValue (int): A value of a section of a date.
    
    Returns:
        str: A date value prepended with a zero if it is single digit.
    """
    if dateValue < 10:
        return "0" + str(dateValue)
    else:
        return str(dateValue)

def getMinutesConfluencePage(committeeMinutesParentPageID:str) -> str:
    child_pages = api.get_child_pages(committeeMinutesParentPageID)

    if len(child_pages) < 1:
        logger.warning("This committee contains no child pages. " + committeeMinutesParentPageID)
        return None

    for page in child_pages:
        if "minutes" in page["title"].lower():
            return page["id"]

    logger.warning("This committee contains no Minutes page. " + committeeMinutesParentPageID)
    return None

def uploadCommitteeMinute(committeeMinutesAgendaFilePath:str, committeeMinutesTopicsFilePath:str, commmitteeMinutesParentPageID:str, committee_name:str, committeeSpaceID:str = "COMM"):
    """
    Build a ConfluencePage using parameters and upload that page to the correct
    space and page.
    Args:
        committeeMinutesAgendaFilePath (str): File path of the minutes file.
        committeeMinutesTopicsFilePath (str): File path of the agenda file.
        commmitteeMinutesParentPageID (str): Confluence Page ID of a parent.
        committeeSpaceID (str, optional): Defaults to "COMM". The committees spaceID.
    """

    committee_base_url = credentials.getCommitteesDirectory()

    attendees_file_path = "\\".join([committee_base_url, committee_name, committeeMinutesAgendaFilePath])
    minutes_file_path = "\\".join([committee_base_url, committee_name, committeeMinutesTopicsFilePath])
    
    attendees_lines = None
    agenda_lines = None

    with(open(attendees_file_path, "r", encoding="utf-8")) as agenda_file:
        #\0x9d
        agenda_lines = [line for line in agenda_file]

    with(open(minutes_file_path, "r", encoding="utf-8")) as minutes_file:
        attendees_lines = [line for line in minutes_file]
    
    attendees = getAttendees(attendees_lines)
    agenda = getAgenda(agenda_lines)

    if attendees == None or agenda == None:
        return

    presenters = []

    for presenterIndex in range(len(attendees["Topics"])):
        presenters.append({
            "Topic": agenda["Agenda"][presenterIndex],
            "Presenter": agenda["Presenters"][presenterIndex]
        })

    parsed_minute = buildMinute(
            committee_name, 
            agenda["Minutes Date"], 
            attendees["Members Attending"], 
            attendees["Members NOT Attending"], 
            attendees["Others Attending"], 
            presenters,
            attendees["Topics"])


    title = committee_name + " - Minutes - " + agenda["Minutes Date"]

    payload = parsed_minute.replace("\\r\\n", "").replace("&", "and").replace(b"\0x9d", "'")

    minutes_child_page = getMinutesConfluencePage(commmitteeMinutesParentPageID)

    result = api.create_page(committeeSpaceID, title, payload, str(minutes_child_page))
    debugging.pause()
    


def getPageIDFromCommitteeName(committee_name:str, committee_parent_page_id:int = 1278261):
    committees = api.request(
        method="GET",
        path="rest/api/content/" + str(committee_parent_page_id) + "/child/page"
    )

    if committees.status_code == 200:
        committees = committees.json()["results"]
        committee_ids = [committee["id"] for committee in committees if committee_name.lower() in committee["title"].lower()]

        if len(committee_ids) < 1:
            logger.warning("No committees exist with that name on Confluence. " + committee_name)
            return []
        elif len(committee_ids) > 1:
            logger.warning("More than one committe with that name on Confluence." + committee_name)
            return committee_ids
        else:
            return committee_ids[0]
    else:
        return []
    return []

def getCommitteesFromFileSystem() -> list:
    """
    Get a list of committee folder paths within the given parentDirectory.

        parentDirectory (str, optional): Defaults to
    "/home/njennings/minutes_pdfs". The path to the output of the committee downloads.
    
    Returns:
        list: A list of absolute folder paths for each committee.
    """

    parent_directory = credentials.getCommitteesDirectory()

    return [
        "\\".join([parent_directory, folder]) 
        for folder in os.listdir(parent_directory) 
        if os.path.isdir("\\".join([parent_directory, folder]))
    ]

def getFilesFromCommittee(committee:str) -> list:
    """
    Get a list of files within a given committee folder path.
    
    Args:
        committee (str): A committee folder path.
    
    Returns:
        list: A list of files with absolute paths within a committee folder.
    """
    return ["/".join([committee, committeeFile]) for committeeFile in os.listdir(committee)]

def getDateFromFile(file_name:str) -> list:
    results = re.search(r"\d{1,2}(\/|-|_)\d{1,2}(\/|-|_)(\d{4}|\d{2})", file_name)

    if results == None:
        return []

    if len(results.groups()) > 0:
        first_occurrence = results.group(0)
        return re.split(r"-|\/|_", first_occurrence)

def padYear(year:str):
    if len(year) == 2 and year[0] == "0":
        return "20" + year
    else:
        return year


def getFilesWithSimilarDate(file_name:str, agendas_list:list) -> list:

    minute_date = getDateFromFile(file_name)

    if len(minute_date) < 1:
        logger.warning(file_name + " has no date.")
        return []

    minute_month = minute_date[0]
    minute_day = minute_date[1]
    minute_year = padYear(minute_date[2])

    matches = []

    for agenda in agendas_list:

        agenda_date = getDateFromFile(agenda)

        if len(agenda_date) < 1:
            continue

        agenda_month = agenda_date[0]
        agenda_day = agenda_date[1]
        agenda_year = padYear(agenda_date[2])

        if (minute_month == agenda_month 
        and minute_day  == agenda_day
        and minute_year == agenda_year):
            matches.append(agenda)

    return matches




def mergeMatches():
    """
    The test method for pairing a minutes file with an agenda file for
    eventually merging into a single page on Confluence.
    """
    committees = getCommitteesFromFileSystem()

    for committee in committees:

        committee_pieces = committee.split("\\")
    
        if len(committee_pieces) < 1:
            logger.critical("No committee name collected from " + committee)
            continue 

        committee_name = committee_pieces[-1]

        minutes = getMinutesFromFolder(committee)
        agendas = getAgendasFromFolder(committee)

        for file in minutes:

            current_file_name = file.split("/")[-1]
            
            matches = getFilesWithSimilarDate(file, agendas)

            if len(matches) <= 0:
                logger.warning("No matches for file " + current_file_name)
                continue
            elif len(matches) > 1:
                logger.warning("More than one match for file " + current_file_name)
                continue

            only_match = matches[0]

            logger.info("Matching " + current_file_name + " to " + only_match)

            committee_id = getPageIDFromCommitteeName(committee_name)

            uploadCommitteeMinute(only_match, file, committee_id, committee_name)

mergeMatches()
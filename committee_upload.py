import requests, urllib3, os, dateutil, time, string, logging, time, json, re, credentials, debugging
from atlassian import Confluence
from os import listdir
from os.path import isfile, join, isdir, exists
from datetime import datetime

urllib3.disable_warnings()
log = logging.getLogger('atlassian')
log.setLevel(logging.CRITICAL)

api = credentials.generateSession()

def getAgenda(lines_of_file:str) -> dict:
    """
    Read the lines of a file and get the information about the agenda.

    {
        "Agenda": agenda,
        "Presenters": presenters,
        "Minutes Date": minutesDate,
        "Committee Name": committee_name
    }
    
    Args:
        lines_of_file (list): A list of strings from a file.
    
    Returns:
        dict: A dictionary like above.
    """
    agenda = []
    presenters = []
    minutesDate = ""
    agendaSection = False
    presenterSection = False

    committee_name = ""
    line_index = 0

    lastTopic = ""

    for line in lines_of_file:
        if "Outcome".lower() in line.lower():
            agendaSection = True
            continue

        if "Presenter".lower() in line.lower():
            agendaSection = False
            presenterSection = True
            continue
        
        if "Desired Outcome".lower() in line.lower():
            presenterSection = False
            continue

        if len(line) < 1:
            continue

        if line_index == 1:
            committee_name = line.strip().replace("Meeting of the ", "")
            print(committee_name)
        

        if re.match(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s(January|February|March|April|May|June|July|August|September|October|November|December)\s\d+,\s\d{4}", line):
            date_formatted = line.split("at")[0].strip()
            date_formatted = datetime.strptime(date_formatted, "%A, %B %d, %Y").date()
            date_formatted = date_formatted.strftime("%m/%d/%y")
            minutesDate = date_formatted


        if presenterSection:
            if len(line.strip()) > 0 and not(re.match(r"(D|I|V)[^(a-z)]", line)):
                presenters.append(line.strip())
                
        if agendaSection:
            if lastTopic == "" and re.match(r"(\d\d|\d).\s.+", line.strip()):
                lastTopic = line.replace("\n", " ")
            elif lastTopic != "" and not(re.match(r"(\d\d|\d).\s.+", line.strip())):
                lastTopic += line
            elif lastTopic != "" and re.match(r"(\d\d|\d).\s.+", line.strip()):
                cleanedTopic = lastTopic.replace("\n", " ")
                cleanedTopic = re.sub(r"(\d|\d\d)\.\s", "", cleanedTopic).strip()
                agenda.append(cleanedTopic)
                lastTopic = line
        line_index += 1
            
        if re.match(r"(\d\d|\d).\s.+", lastTopic.strip()):
            cleanedTopic = lastTopic.replace("\n", " ")
            cleanedTopic = re.sub(r"(\d|\d\d)\.\s", "", cleanedTopic).strip()
            cleanedTopic = re.sub(r"[D|I|V]*\/*[D|I|V]*\/*[D|I|V]", "", cleanedTopic)
            agenda.append(cleanedTopic.strip())

    return {
        "Agenda": agenda,
        "Presenters": presenters,
        "Minutes Date": minutesDate,
        "Committee Name": committee_name
    }

def getAttendees(lines_in_file:str) -> dict:
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
    
    return {
        "Members Attending": committeeMembersAttending,
        "Members NOT Attending": committeeMembersNotAttending,
        "Others Attending": othersAttending,
        "Topics": committeeTopics
    }


def committeeMinutes(topics:list) -> str:
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

def committeeAttending(attending:list, notattending:list, otherattending:list) -> str:
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

def committeeAgenda(agenda:list) -> str:
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

def committeeStatus(committeeName:str, minutesDate:str, committeeStatus:str) -> str:
    """
    Get the status of a paticular committee.
    
    Args:
        committeeName (str): The name of a committee
        minutesDate (str): The date of a particular minutes
    committeeStatus (str): The status of a paticular committee as "Approved"
    "
    
    Returns:
        str: A page block represnting the status of a committee.
    """

    beginning = "<ac:structured-macro ac:name=\"content-block\" ac:schema-version=\"1\" ac:macro-id=\"71c4d118-3da1-4e97-8e1d-f2faf9b45d0f\"><ac:parameter ac:name=\"id\">1856481235</ac:parameter><ac:parameter ac:name=\"class\">minutes-meta</ac:parameter><ac:rich-text-body><ac:structured-macro ac:name=\"details\" ac:schema-version=\"1\" ac:macro-id=\"6561762b-bb94-4120-b624-82bc63b5fd28\"><ac:parameter ac:name=\"id\">minutesandagenda</ac:parameter><ac:rich-text-body>"
        
    table = "<table class=\"wrapped\"><colgroup><col /><col /></colgroup><tbody><tr><th><p>Committee Name</p></th><td><p>"
    table += committeeName + "</p></td></tr><tr><th><p>Date</p></th><td><p>"

    table += minutesDate + "</p></td></tr><tr><th><p>Status</p></th><td><div class=\"content-wrapper\"><ac:structured-macro ac:name=\"minutestatus\" ac:schema-version=\"1\" ac:macro-id=\"1c0ed33a-a4c3-48f4-9a49-4b1a9735e9bf\"><ac:parameter ac:name=\"atlassian-macro-output-type\">INLINE</ac:parameter><ac:rich-text-body><p>"
    table += committeeStatus + "</p></ac:rich-text-body></ac:structured-macro></div></td></tr></tbody></table>"
        
    closing = "</ac:rich-text-body></ac:structured-macro></ac:rich-text-body></ac:structured-macro>"
    
    return beginning + table + closing



def buildMinute(
    committeeName:str,
    committeeMinutesDate:str,
    committeeMinutesAttending:list, 
    committeeMinutesNotAttending:list, 
    committeeMinutesOtherAttending:list,
    cAgenda:list,
    committeeTopics:list,
    committeeMinutesStatus:str = "Approved") -> str:

    """
    Return a string representation of a ConfluencePage which can be uploaded to
    Confluence.
    """
    
    beginning = "<ac:structured-macro ac:name=\"content-layer\" ac:schema-version=\"1\" ac:macro-id=\"9dec53ff-ddd1-4959-824f-4f1ae61c797a\"><ac:parameter ac:name=\"id\">1856481233</ac:parameter><ac:rich-text-body><ac:structured-macro ac:name=\"content-column\" ac:schema-version=\"1\" ac:macro-id=\"2c808257-9edf-40b1-a12d-466b68e25950\"><ac:parameter ac:name=\"id\">1856481236</ac:parameter><ac:rich-text-body>"
        
    content = str(committeeStatus(committeeName, committeeMinutesDate, committeeMinutesStatus))
    content += str(committeeAgenda(cAgenda))
    content += str(committeeAttending(committeeMinutesAttending, committeeMinutesNotAttending, committeeMinutesOtherAttending))
    content += str(committeeMinutes(committeeTopics))

    closing = "</ac:rich-text-body></ac:structured-macro></ac:rich-text-body></ac:structured-macro>"
    
    return beginning + content + closing

def uploadMinutes(folder:str = "/home/njennings/minutes_pdfs"):

    attendees = getAttendees()
    agenda = getAgenda()
    
    presenters = []

    for presenterIndex in range(len(attendees["Topics"])):
        presenters.append({
            "Topic": agenda["Agenda"][presenterIndex],
            "Presenter": agenda["Presenters"][presenterIndex]
        })


    minutes_page = buildMinute(
        agenda["Committee Name"], 
        agenda["Minutes Date"], 
        attendees["Members Attending"], 
        attendees["Members NOT Attending"], 
        attendees["Others Attending"], 
        presenters,
        attendees["Topics"])

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

def uploadCommitteeMinute(committeeMinutesAgendaFilePath:str, committeeMinutesTopicsFilePath:str, commmitteeMinutesParentPageID:str, committeeSpaceID:str = "COMM"):
    """
    Build a ConfluencePage using parameters and upload that page to the correct
    space and page.
    Args:
        committeeMinutesAgendaFilePath (str): File path of the minutes file.
        committeeMinutesTopicsFilePath (str): File path of the agenda file.
        commmitteeMinutesParentPageID (str): Confluence Page ID of a parent.
        committeeSpaceID (str, optional): Defaults to "COMM". The committees spaceID.
    """

    attendees = getAttendees(committeeMinutesTopicsFilePath)
    agenda = getAgenda(committeeMinutesAgendaFilePath)

    presenters = []

    for presenterIndex in range(len(attendees["Topics"])):
        presenters.append({
            "Topic": agenda["Agenda"][presenterIndex],
            "Presenter": agenda["Presenters"][presenterIndex]
        })

    parsed_minute = buildMinute(
            agenda["Committee Name"], 
            agenda["Minutes Date"], 
            attendees["Members Attending"], 
            attendees["Members NOT Attending"], 
            attendees["Others Attending"], 
            presenters,
            attendees["Topics"])


    title = "Committees - " + agenda["Committee Name"] + " - Minutes - " + agenda["Minutes Date"]

    payload = parsed_minute.replace("\\r\\n", "").replace("&", "and")

    payload = ''.join(filter(lambda c: c in printable, payload))

    with open("C:\\Users\\njennings\\Atom\\minutes_tests\\minutes_test.json", "w") as file:
        file.write(payload)

    api.create_page(committeeSpaceID, title, payload, str(commmitteeMinutesParentPageID))

def getPageIDFromCommitteeName(committee:str, committee_parent_page_id:int = 1278261):
    committees = api.request(
        method="GET",
        path="rest/api/content/" + str(committee_parent_page_id) + "/child/page"
    )

    if committees.status_code == 200:
        committee = committees.json()["results"]

        if committees and len(committees) > 0:
            return (committees["id"] for committee in committees if committee.lower() in committee["title"].lower())
        else:
            return []
    else:
        return []

def getCommitteesFromFileSystem(parentDirectory:str = "/home/njennings/minutes_pdfs") -> list:
    """
    Get a list of committee folder paths within the given parentDirectory.

        parentDirectory (str, optional): Defaults to
    "/home/njennings/minutes_pdfs". The path to the output of the committee downloads.
    
    Returns:
        list: A list of absolute folder paths for each committee.
    """
    return [
        "/".join([parentDirectory, folder]) 
        for folder in os.listdir(parentDirectory) 
        if os.path.isdir("/".join([parentDirectory, folder]))
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

def getMatches():
    """
    The test method for pairing a minutes file with an agenda file for
    eventually merging into a single page on Confluence.
    """
    committees = getCommitteesFromFileSystem()
    for committee in committees:
        files = getFilesFromCommittee(committee)
        for f in files:
            current_file_name = f.split("/")[-1]
            matches = matchTwoDates(f)

            if len(matches) != 1:
                continue
            else:
                print("=======================================")
                print("CURRENT COMMITTEE: " + committee + " # files: " + str(len(files)))
                print("CURRENT FILE: " + current_file_name)
                print("=======================================")
                for match in matches:
                    current_match_name = match.split("/")[-1]
                    print(current_match_name)
                pause()
                clear()

def main_minutes():
    
    



    uploadCommitteeMinute(
        "C:\\Users\\njennings\\Atom\\minutes_tests\\m1.txt",
        "C:\\Users\\njennings\\Atom\\minutes_tests\\o1.txt",
        str(8257827)
    )
import requests, urllib3, os, dateutil, time, string, logging, time, json, re, credentials, debugging, unicodedata
from atlassian import Confluence
from os import listdir
from os.path import isfile, join, isdir, exists
from datetime import datetime
confluence_api = credentials.generateSession()
logger = debugging.generateLogger()

def isAgenda(file_name) -> bool:
    return "agenda" in file_name.lower()

def isMinutes(file_name:str) -> bool:
    return "minutes" in file_name.lower()

def isFileEXT(file_name:str, file_ext:str) -> bool:
    return file_name.split(".")[-1] == file_ext

def getAgendasFromFolder(folder_path:str) -> list:

    folder_name = folder_path.split("/")[-1]

    if not os.path.exists(folder_path):
        logger.critical("No folder exists with the name " + folder_name)
        return None
    if not os.path.isdir(folder_path):
        logger.critical(folder_name + " is not a directory.")
        return None

    agendas = (file for file in os.listdir(folder_path) if isAgenda(file) and isFileEXT(file, "txt"))
    
    return agendas

def getMinutesFromFolder(folder_path:str) -> list:

    folder_name = folder_path.split("/")[-1]

    if not os.path.exists(folder_path):
        logger.critical("No folder exists with the name " + folder_name)
        return None
    if not os.path.isdir(folder_path):
        logger.critical(folder_name + " is not a directory.")
        return None
    
    minutes = (file for file in os.listdir(folder_path) if isMinutes(file) and isFileEXT(file, "txt"))
    
    return minutes

def clean_minutes_from_committees(committee_names):
    for committee_name in committee_names:
        committee_id = getPageIDFromCommitteeName(committee_name)
        minutes_page_id = getMinutesConfluencePage(committee_id)
        pages = confluence_api.get_child_pages(minutes_page_id)
        while len(pages) > 0:
            page_ids = [page["id"] for page in pages]
            for index, page in enumerate(page_ids, 1):
                confluence_api.remove_page(page)
                logger.info("Cleaned " + str(index) + "/" + str(len(page_ids)))
            pages = confluence_api.get_child_pages(minutes_page_id)
        logger.info("Done cleaning " + committee_name)

def attach_file(file_path, parent_page_id):
    content_types = {
        ".gif": "image/gif",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".xls": "application/vnd.ms-excel",
    }

    file_extension = os.path.splitext(file_path)[-1]
    file_name = os.path.basename(file_path)
    content_type = content_types.get(file_extension, "application/binary")
    post_path = "rest/api/content/{page_id}/child/attachment".format(page_id=parent_page_id)

    if not os.path.exists(file_path):
        return

    with open(file_path, "rb") as data_file:
        confluence_api.post(
            path=post_path,
            data = {
            "type": "attachment",
            "fileName": file_name,
            "contentType": content_type,
            "comment": " ",
            "minorEdit": "true"
        }, 
        headers = {
            "X-Atlassian-Token": "no-check",
            "Accept": "application/json"
        }, 
        files={
            "file":(file_name, data_file, content_type)
        })    

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
    line_index = 0

    lastTopic = ""

    for line in lines_of_file:

        line_lower = line.lower().strip()
        line_stripped = line.strip()

        if "outcome" in line_lower or "agenda" in line_lower:
            agendaSection = True
            presenterSection = False
            continue
        elif presenterSection and not agendaSection and len(line_lower) < 1:
            agendaSection = True
            presenterSection = False
            continue
        elif "presenter" in line_lower or "leader" in line_lower:
            agendaSection = False
            presenterSection = True
            continue
        elif "desired outcome" in line_lower:
            presenterSection = False
            continue
        elif len(line_lower) < 1:
            continue
        
        regex_long_form_date = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s\d+,\s\d{4}"
        regex_starts_with_number = r"(\d\d|\d).\s.+"
        regex_only_number = r"(\d\d|\d)(\.|\))\s"
        regex_is_table_label = r"[D|I|V]*\/*[D|I|V]*\/*[D|I|V]"
        confluence_preffered_date_format = "%m/%d/%y"
        file_regex_date_format = "%B %d, %Y"

        if line_index < 5:
            search_for_date = re.search(regex_long_form_date, line)
            if search_for_date:
                if len(search_for_date.groups()) > 0:
                    matched_date_str = search_for_date.group(0)
                    matched_date = datetime.strptime(matched_date_str, file_regex_date_format)
                    minutes_date = matched_date.strftime(confluence_preffered_date_format)


        if presenterSection:
            if len(line_stripped) > 0 and not re.match(r"(D|I|V)[^(a-z)]", line):
                presenters.append(line_stripped)
        
        if agendaSection:
            if lastTopic == "" and re.match(regex_starts_with_number, line_stripped):
                lastTopic = line.replace("\n", " ")
            elif lastTopic != "" and not re.match(regex_starts_with_number, line_stripped):
                lastTopic += line
            elif lastTopic != "" and re.match(regex_starts_with_number, line_stripped):
                cleanedTopic = lastTopic.replace("\n", " ")
                agenda.append(cleanedTopic.strip())
                lastTopic = line
            lastTopic = re.sub(regex_only_number, "", lastTopic)
        line_index += 1
            
        if lastTopic != "" and len(lastTopic) < 1 and re.match(regex_starts_with_number, lastTopic.strip()):
            cleanedTopic = lastTopic.replace("\n", " ")
            cleanedTopic = re.sub(regex_is_table_label, "", cleanedTopic)
            agenda.append(cleanedTopic.strip())

    date_failure = not minutes_date or len(minutes_date) < 1
    presenters_failure = not presenters or len(presenters) < 1
    agenda_failure = not agenda or len(agenda) < 1

    if date_failure:
        logger.warning("No date was retrieved for this file.")

    if presenters_failure:
        logger.warning("No presenters were retrieved for this file.")

    if agenda_failure:
        logger.warning("No agenda was retrieved for this file.")

    return {
        "Agenda": agenda if len(agenda) > 0 else [],
        "Presenters": presenters if len(presenters) > 0 else [],
        "Minutes Date": minutes_date if not(minutes_date is None) else "None"
    }

def isName(string):
    length = len(string.split(" "))
    regex_remove_suffix = r"(\(.+\))|(\,.+)"
    if length == 2:
        return True
    else:
        if length < 2:
            return False
        else:
            string_stripped = re.sub(regex_remove_suffix, "", string).strip()
            length = len(string_stripped.split(" "))
            if length == 2:
                return True
            else:
                return False
        

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

    section_committeeMembersAttending = False
    section_committeeMembersNotAttending = False
    section_othersAttending = False
    section_committeeTopics = False

    committeeMembersAttending = []
    committeeMembersNotAttending = []
    othersAttending = []
    committeeTopics = []

    lastLine = ""

    topic = {
        "Topic":"",
        "Description":""
    }

    for index, line in enumerate(lines_in_file, 0):

        line_stripped = line.strip()
        line_lower = line_stripped.lower()

        if len(line_lower) < 1:
            continue

        if "other" in line_lower and "attend" in line_lower and not section_committeeTopics:
            section_othersAttending = True
            section_committeeMembersAttending = False
            section_committeeMembersNotAttending = False
            section_committeeTopics = False
            continue
        elif all(["not" in line_lower, "member" in line_lower]) or all(["not" in line_lower, "attend" in line_lower]) or "absent" in line_lower and not section_committeeTopics:
            section_committeeMembersNotAttending = True
            section_committeeMembersAttending = False
            section_othersAttending = False
            section_committeeTopics = False
            continue
        elif "attendees" in line_lower or "member attendees" in line_lower or all(["attending" in line_lower, "members" in line_lower]):
            section_committeeMembersAttending = True
            section_committeeMembersNotAttending = False
            section_othersAttending = False
            section_committeeTopics = False
            continue
        elif not isName(line_lower) and "attend" not in line_lower and "conference" not in line_lower and index > 10:
            section_committeeTopics = True
            section_othersAttending = False
            section_committeeMembersAttending = False
            section_committeeMembersNotAttending = False
        
        if section_committeeMembersAttending:

            committeeMembersAttending.append(line_stripped)

        elif section_committeeMembersNotAttending:

            committeeMembersNotAttending.append(line_stripped)

        elif section_othersAttending:

            othersAttending.append(line_stripped)

        elif section_committeeTopics:
            if len(lastLine) < 1:

                topic["Description"] = topic["Description"].strip()

                committeeTopics.append(topic)

                topic = {
                    "Topic": line_stripped,
                    "Description": ""
                }

            else:
                topic["Description"] += line.replace("\n", " ")
        lastLine = line_stripped
    
    attending_failure = not committeeMembersAttending or len(committeeMembersAttending) < 1
    not_attending_failure = not committeeMembersNotAttending
    others_attending_failure = not othersAttending
    topics_failure = not committeeTopics or len(committeeTopics) < 1

    if attending_failure:
        logger.warning("Members attending not retrieved.")
    
    if not_attending_failure:
        logger.warning("Members NOT attending not retrieved.")

    if others_attending_failure:
        logger.warning("Others attending not retrieved.")

    if topics_failure:
        logger.warning("Topics not retrieved.")

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

    for topic in topics:
        table += "<h2>" + topic["Topic"] + "</h2>"

        paragraphs = topic["Description"].split("\n\n")

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
        
    for attendee in attending:
        if "\u00e2\u0080\u0093" in attendee:
            temp = ", ".join(attendee.split("\u00e2\u0080\u0093"))
            table += "<tr><td colspan=\"1\">" + temp + "</td></tr>"
        else:
            table += "<tr><td colspan=\"1\">" + attendee + "</td></tr>"

    table += "</tbody></table><table class=\"wrapped\"><colgroup><col /></colgroup><tbody><tr><th>Members Not Attending</th></tr>"
        
    for notattendee in notattending:
        table += "<tr><td colspan=\"1\">" + notattendee + "</td></tr>"
    
    table += "</tbody></table><table class=\"wrapped\"><colgroup><col /></colgroup><tbody><tr><th>Others Attending</th></tr>"
        
    for otherattendee in otherattending:
        table += "<tr><td colspan=\"1\">" + otherattendee + "</td></tr>"
            
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

    for topic in agenda:
        table += "<tr><td colspan=\"1\">" + " - ".join(str(topic["Topic"]).split("\u00e2\u20ac\u201c")) + "</td><td colspan=\"1\">" + str(topic["Presenter"]) + "</td></tr>"
    
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

    attachments = "<ac:structured-macro ac:name=\"content-block\" ac:schema-version=\"1\" ac:macro-id=\"6ace2570-bb93-4cf2-ae05-78089be52874\"><ac:parameter ac:name=\"id\">270750570</ac:parameter><ac:rich-text-body><ac:structured-macro ac:name=\"info\" ac:schema-version=\"1\" ac:macro-id=\"22d834ad-6fbb-45a2-9463-a442198deb8f\"><ac:rich-text-body><p>Content on this page has been automatically generated from the source document(s) below.</p></ac:rich-text-body></ac:structured-macro><p><ac:structured-macro ac:name=\"attachments\" ac:schema-version=\"1\" ac:macro-id=\"a4ce25c3-a4d4-46ae-9b67-db7946e86b05\" /></p></ac:rich-text-body></ac:structured-macro>"

    return beginning + table + closing + attachments



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
    if int(dateValue) < 10:
        return "0" + str(dateValue)
    else:
        return str(dateValue)

def getMinutesConfluencePage(committeeMinutesParentPageID:str) -> str:

    if not committeeMinutesParentPageID:
        logger.warning("No committeeMinutesParentPageID supplied.")
        return None

    child_pages = confluence_api.get_child_pages(committeeMinutesParentPageID)

    if not child_pages or len(child_pages) < 1:
        logger.warning("This committee contains no child pages. " + committeeMinutesParentPageID)
        return None

    for page in child_pages:
        if "minutes" in page["title"].lower():
            return int(page["id"])

    logger.warning("This committee contains no Minutes page. " + committeeMinutesParentPageID)
    return None

def sanatizeControlCharacters(characters):
    return "".join(ch for ch in characters if unicodedata.category(ch)[0] != "C")

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

    if not committeeMinutesAgendaFilePath:
        committeeMinutesAgendaFilePath = ""

    if not committeeMinutesTopicsFilePath:
        committeeMinutesTopicsFilePath = ""

    committee_minutes_file_name_no_ext = committeeMinutesTopicsFilePath.split("\\")[-1].split(".")[0]
    committee_agenda_file_name_no_ext = committeeMinutesAgendaFilePath.split("\\")[-1].split(".")[0]

    pdf_extension = ".pdf"
    txt_extension = ".txt"

    minute_date = getDateFromFile(committeeMinutesTopicsFilePath)

    if len(minute_date) < 1:
        minute_date = [0, 0, 0]

    minute_date[0] = padMonthOrDay(minute_date[0])
    minute_date[1] = padMonthOrDay(minute_date[1])
    minute_date[2] = padYear(minute_date[2])
    minute_date = "/".join(minute_date)

    committee_file_path = "\\".join([committee_base_url, committee_name])

    attendees_file_path_txt = "\\".join([committee_file_path, committee_agenda_file_name_no_ext]) + txt_extension
    minutes_file_path_txt = "\\".join([committee_file_path, committee_minutes_file_name_no_ext]) + txt_extension

    attendees_file_path_pdf = "\\".join([committee_file_path, committee_agenda_file_name_no_ext]) + pdf_extension
    minutes_file_path_pdf = "\\".join([committee_file_path, committee_minutes_file_name_no_ext]) + pdf_extension

    committee_agenda_empty = len(committee_agenda_file_name_no_ext) < 1
    committee_minutes_empty = len(committee_minutes_file_name_no_ext) < 1

    attendees = None
    agenda = None
    attendees_lines = None
    agenda_lines = None

    if not committee_agenda_empty:
        with(open(attendees_file_path_txt, "r", encoding="utf-8")) as agenda_file:
            agenda_lines = list(line for line in agenda_file)
            agenda = getAgenda(agenda_lines)
    else:
        logger.warning("Attendees object not present.")

    if not committee_minutes_empty:
        with(open(minutes_file_path_txt, "r", encoding="utf-8")) as minutes_file:
            attendees_lines = list(line for line in minutes_file)
            attendees = getAttendees(attendees_lines)
    else:
        logger.warning("Agenda object not present.")

    presenters = []

    if not committee_agenda_empty:
        for topic in agenda["Agenda"]:
            presenters.append({
                "Topic": topic,
                "Presenter": ""
            })

    if agenda and attendees and len(attendees["Topics"]) > 0:

        parsed_minute = buildMinute(
            committee_name, 
            minute_date, 
            attendees["Members Attending"], 
            attendees["Members NOT Attending"], 
            attendees["Others Attending"], 
            presenters,
            attendees["Topics"])

    else:

        with open(minutes_file_path_txt, "r", encoding="utf8") as minute_file_contents:
            parsed_minute = buildMinute(
                committee_name,
                minute_date,
                attendees["Members Attending"] if attendees else [], 
                attendees["Members NOT Attending"] if attendees else [], 
                attendees["Others Attending"] if attendees else [], 
                presenters or [],
                [{"Topic":"Topics", "Description": "".join(minute_file_contents)}]
            )


    title = committee_name + " - Minutes - " + minute_date

    payload = parsed_minute.replace("\r", "&#13;").replace("&", "&amp;").replace("â€™", "&apos;").replace("\f", "<br/>").replace("\n", "<br/>")
    payload = sanatizeControlCharacters(payload)

    minutes_child_page = getMinutesConfluencePage(commmitteeMinutesParentPageID)

    if not minutes_child_page:
        logger.error("Could not retrieve the 'Minutes' child page from parent.")
        return
 
    resulting_page = confluence_api.create_page(committeeSpaceID, title, payload, int(minutes_child_page))

    try:
        resulting_page_id = resulting_page["id"]
        logger.info("Successfully uploaded " + resulting_page_id + ".")
    except KeyError:
        logger.warning("Confluence Page already exists.")

    try:
        confluence_api.set_page_label(resulting_page_id, "minutes")
    except UnboundLocalError:
        logger.error("Can't set label to page.")

    try:
        attach_file(attendees_file_path_pdf, int(resulting_page_id))
        attach_file(minutes_file_path_pdf, int(resulting_page_id))
    except UnboundLocalError:
        logger.error("Can't upload attachments to page.")

def getPageIDFromCommitteeName(committee_name:str, committee_parent_page_id:int = 1278261):
    committees = confluence_api.request(
        method="GET",
        path="rest/api/content/" + str(committee_parent_page_id) + "/child/page"
    )

    if committees.status_code == 200:
        committees = committees.json()["results"]
        committee_ids = list(committee["id"] for committee in committees if committee_name.lower() in committee["title"].lower())

        if len(committee_ids) < 1:
            logger.warning("No committees exist with that name on Confluence. " + committee_name)
            return None
        elif len(committee_ids) > 1:
            logger.warning("More than one committe with that name on Confluence." + committee_name)
            return None
        else:
            return committee_ids[0]
    else:
        return None
    return None

def getCommitteesFromFileSystem() -> list:
    """
    Get a list of committee folder paths within the given parentDirectory.

        parentDirectory (str, optional): Defaults to
    "/home/njennings/minutes_pdfs". The path to the output of the committee downloads.
    
    Returns:
        list: A list of absolute folder paths for each committee.
    """

    parent_directory = credentials.getCommitteesDirectory()

    return (
        "\\".join([parent_directory, folder]) 
        for folder in os.listdir(parent_directory) 
        if os.path.isdir("\\".join([parent_directory, folder]))
    )

def getFilesFromCommittee(committee:str) -> list:
    """
    Get a list of files within a given committee folder path.
    
    Args:
        committee (str): A committee folder path.
    
    Returns:
        list: A list of files with absolute paths within a committee folder.
    """
    return ("/".join([committee, committeeFile]) for committeeFile in os.listdir(committee))

def getDateFromFile(file_name:str) -> list:

    regex_valid_date = r"\d{1,2}(\/|-|_)\d{1,2}(\/|-|_)(\d{4}|\d{2})"
    regex_date_seperators = r"-|\/|_"

    results = re.search(regex_valid_date, file_name)

    if not results:
        return []

    if len(results.groups()) > 0:
        first_occurrence = results.group(0)
        return re.split(regex_date_seperators, first_occurrence)

def padYear(year:str):
    if len(str(year)) == 2 and year[0] == "0":
        return "20" + str(year)
    else:
        return str(year)


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

        if committee_name in ["Guaranty Funds Information Systems", "IT Advisory & Governance"]:
            continue

        minutes = getMinutesFromFolder(committee)
        agendas = getAgendasFromFolder(committee)

        for file in minutes:

            current_file_name = file.split("/")[-1]
            
            matches = getFilesWithSimilarDate(file, agendas)

            committee_id = getPageIDFromCommitteeName(committee_name)

            if len(matches) <= 0:
                logger.warning("No matches for file " + current_file_name)
                uploadCommitteeMinute(None, file, committee_id, committee_name)
            elif len(matches) > 1:
                logger.warning("More than one match for file " + current_file_name)
            else:
                only_match = matches[0]

                logger.info("Matching " + current_file_name + " to " + only_match)

                if not committee_id:
                    logger.error("Could not get committee_id from name " + committee_name)
                else:
                    uploadCommitteeMinute(only_match, file, committee_id, committee_name)
        logger.info("Completed importing " + committee_name + ".")
        #debugging.pause()

cleaning_committee_names = [
        "Accounting Issues Committee",#
        "Best Practices Committee",
        "Board Audit Committee",#
        "Corporate Governance Committee",#
        "Finance Committee",
        "Bylaws Committee",#
        "Communication Committee",#
        "Coordinating Committee Chairs Committee",#
        "Core Services Committee",
        "Education Committee",#
        "Legal Committee",#
        "Member Committee Advisory Committee",#
        "NCIGF Services Committee",#
        "Nominating Committee",
        "Operations Committee",#
        "Public Policy Committee",#
        "Site Selection Committee",#
        "Special Funding Committee"
]

clean_minutes_from_committees(cleaning_committee_names)
mergeMatches()
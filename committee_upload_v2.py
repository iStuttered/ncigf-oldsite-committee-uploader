import requests, urllib3, os, dateutil, time, string, logging, time, json, re, credentials, debugging
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

def begin_merging_process():
    debugging.clear()

    for committee_folder in getCommitteesFromFileSystem():
        for minutes_file in getMinutesFromFolder(committee_folder):
            print()

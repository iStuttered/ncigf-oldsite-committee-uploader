import os, sys, logging, urllib3, inspect

def pause():
    """
    Breakpoint for code tests.
    """
    input(" ----- Pause -----")

def clear():
    """
    A console.clearScreen() for easier console viewing.
    """
    os.system("cls")

def generateLogger() -> logging.Logger:

    urllib3.disable_warnings()
    log = logging.getLogger('atlassian')
    log.setLevel(logging.CRITICAL)

    project_name = os.path.dirname(os.path.realpath(__file__)).split("\\")[-1]

    logger = logging.getLogger(project_name)
    logger.setLevel(logging.INFO)

    stream = logging.StreamHandler()
    stream.setLevel(logging.INFO)

    formatter = logging.Formatter("%(levelname)s : %(message)s\t- - -\tfrom %(funcName)s line %(lineno)d")

    stream.setFormatter(formatter)

    logger.addHandler(stream)

    return logger
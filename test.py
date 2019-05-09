from atlassian import Confluence
import credentials, debugging
import os

confluence_api = credentials.generateSession()

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

    with open(file_path, "rb") as data_file:
        response = confluence_api.post(
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




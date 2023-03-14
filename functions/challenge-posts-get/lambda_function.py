# NOTES:
# The pagination mechanism is untested as putting the system under a load that 
# would cause DynamoDB queries to start paginating would incur too many costs

#TODO: Fetch last 2 comments for each post

import boto3
import json
import base64
from io import BytesIO

from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeDeserializer

from botocore.exceptions import ClientError


POSTS_TABLE_INDEX = "Status-CommentCount-index"
COMMENTS_TABLE_INDEX = "PostID-Timestamp-index"
IMAGES_BUCKET = "akhomchanka-challenge-images"
POSTS_TABLE = "challenge_posts"
COMMENTS_TABLE = "challenge_comments"
DEFAULT_ITEM_LIMIT = 5

# Resource clients
s3 = boto3.resource("s3")
dynamodb = boto3.resource("dynamodb")

def lambda_handler(event, context):
    run_id = context.aws_request_id
    
    def log(entry):
        """
        The log function adds a run_id header to each log record, 
        making log searches through the log group easier in the future
        """
        print(f"[{run_id}] {entry}")
        
    # Relevant resources -------------------------------------------------------
    images_bucket = s3.Bucket(IMAGES_BUCKET)
    posts_table = dynamodb.Table(POSTS_TABLE)
    comments_table = dynamodb.Table(COMMENTS_TABLE)
    # --------------------------------------------------------------------------
    
    # Check if pagination key has been supplied with the request
    query_params = event.get('queryStringParameters', {})
    pagination_key = query_params.get('nextPage')
    if pagination_key:
        log("Got the pagination key")
        pagination_key = json.loads(pagination_key)
    else:
        log("No pagination key")
    
    # Check if the limit of returned posts has been supplied
    # If not - set the default value
    limit = query_params.get('limit')
    if not limit:
        limit = DEFAULT_ITEM_LIMIT
    else:
        limit = int(limit)
    
    # Proceed from the last position if necessary
    if not pagination_key:
        print("NO PAGINATION")
        try:
            response = posts_table.query(
                IndexName=POSTS_TABLE_INDEX,
                KeyConditionExpression=Key("Status").eq("ok"),
                ScanIndexForward=False,
                Limit=limit
            )
        except ClientError as err:
            log(f"Error while fetching posts: {err}")
            return {
                "statusCode": 500,
                "body": json.dumps({"run_id": run_id, "error_stage": "post_fetching"})
            }
    else:
        print(f"PAGINATION: {pagination_key}")
        try:
            response = posts_table.query(
                IndexName=POSTS_TABLE_INDEX,
                KeyConditionExpression=Key("Status").eq("ok"),
                ScanIndexForward=False,
                ExclusiveStartKey=pagination_key,
                Limit=limit
            )
        except ClientError as err:
            log(f"Error while fetching posts: {err}")
            return {
                "statusCode": 500,
                "body": json.dumps({"run_id": run_id, "error_stage": "post_fetching"})
            }

    print(f"RESPONSE: {response}")
    
    # Convert types to serializable and fetch image content
    # TODO: fetch two latest comments using the corresponding index
    pagination_key = response.get('LastEvaluatedKey')
    if pagination_key:
        log("Got a new pagination key")
        pagination_key["Timestamp"] = int(pagination_key["Timestamp"])
        pagination_key["CommentCount"] = int(pagination_key["CommentCount"])
    items = response["Items"]
    for item in items:
        # Fetch comments for the post
        comment_items = comments_table.query(
            KeyConditionExpression=Key("PostID").eq(item["PostID"]),
            IndexName=COMMENTS_TABLE_INDEX,
            ScanIndexForward=False,
            Limit=2
        )
        for comment in comment_items["Items"]:
            comment["Timestamp"] = int(comment["Timestamp"])
        item["LastComments"] = comment_items["Items"]
        log(f"COMMENT ITEMS: {comment_items}")
        item["Timestamp"] = int(item["Timestamp"])
        item["Version"] = int(item["Version"])
        item["CommentCount"] = int(item["CommentCount"])
        image_object = BytesIO()
        try:
            image_name = item["PostID"] + ".jpg"
            log(f"Downloading image: {image_name}")
            response = images_bucket.download_fileobj(image_name, image_object)
            log(f"Image download response: {response}")
            log(f"Image object: {image_object}")
        except ClientError as err:
            log(f"Error while downloading image: {err}")
            return {
                "statusCode": 500,
                "body": json.dumps({"run_id": run_id, "error_stage": "image_fetching"})
            }
        image_bytes = image_object.getvalue()
        log(f"Image bytes: {image_bytes}")
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        item["Image"] = image_b64
        
    response = {
        "nextPage": pagination_key,
        "posts": items
    }

    # Default successful case
    return {
        "statusCode": 200,
        "body": json.dumps(response)
    }

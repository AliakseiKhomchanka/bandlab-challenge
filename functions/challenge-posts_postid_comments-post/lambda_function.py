import boto3
import json
from time import time

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError


POSTS_TABLE = "challenge_posts"
COMMENTS_TABLE = "challenge_comments"

# Resource clients
dynamodb = boto3.resource("dynamodb")

def lambda_handler(event, context):
    run_id = context.aws_request_id
    body = json.loads(event["body"])
    
    def log(entry):
        """
        The log function adds a run_id header to each log record, 
        making log searches through the log group easier in the future
        """
        print(f"[{run_id}] {entry}")
    
    # Relevant resources -------------------------------------------------------
    posts_table = dynamodb.Table(POSTS_TABLE)
    comments_table = dynamodb.Table(COMMENTS_TABLE)
    #---------------------------------------------------------------------------
    
    # The run ID of the function will be used as the ID of the comment
    comment_id = context.aws_request_id
    post_id = event["pathParameters"]["post_id"]
    
    # Add the post record to the DynamoDB table
    record = {
        "CommentID": comment_id,
        "Timestamp": int(time()),
        "Author": body["author"],
        "Body": body["body"],
        "PostID": post_id
    }
    try:
        comments_table.put_item(Item=record)
    except ClientError as err:
        log(f"Error while updating the comment table: {err}")
        return {
            "statusCode": 500,
            "body": json.dumps({"run_id": run_id, "error_stage": "comment_table_update"})
        }
    
    # Update the comment count in the posts table
    # First get the post record
    #post_record = posts_table.get_item(Key={"PostID": post_id})['Item']
    try:
        response = posts_table.query(
            KeyConditionExpression=Key("PostID").eq(post_id)
        )
    except ClientError as err:
        log(f"Error while fetching post record: {err}")
        return {
            "statusCode": 500,
            "body": json.dumps({"run_id": run_id, "error_stage": "post_fetching"})
        }
    post_record = response["Items"][0]
    post_version = post_record["Version"]
    post_record["Version"] += 1
    post_record["CommentCount"] += 1
    
    # Attempt to write until the version matches
    # Not too fond of doing optimstic locking this way as I can't track
    # actual errors resulting in a ClientError, but for a proof-of-concept it will do
    while True:
        try:
            response = posts_table.put_item(
                Item=post_record,
                ConditionExpression=Attr("Version").eq(post_version)
            )
        except ClientError as err:
            if err.response["Error"]["Code"] == 'ConditionalCheckFailedException':
                post_record["Version"] += 1
                continue
        break

    # Standard successful case
    return {
        "statusCode": 201,
        "body": json.dumps(record)
    }
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
    
    comment_id = event["pathParameters"]["comment_id"]
    post_id = event["pathParameters"]["post_id"]
    
    try:
        response = comments_table.query(
            KeyConditionExpression=Key("CommentID").eq(comment_id)
        )
    except ClientError as err:
        log(f"Error while fetching the comment: {err}")
        return {
            "statusCode": 500,
            "body": json.dumps({"run_id": run_id, "error_stage": "comment_fetching"})
        }
    
    comment_to_delete = {}
    comment_to_delete["CommentID"] = response["Items"][0]["CommentID"]
    comment_to_delete["Timestamp"] = int(response["Items"][0]["Timestamp"])
    print(f"COMMENT TO DELETE: {comment_to_delete}")
    # Remove the comment record
    try:
        comments_table.delete_item(
                    Key=comment_to_delete
        )
    except ClientError as err:
        log(f"Error while deleting the comment record: {err}")
        return {
            "statusCode": 500,
            "body": json.dumps({"run_id": run_id, "error_stage": "comment_deletion"})
        }
    
    # Update the comment count in the posts table
    # First get the post record
    try:
        response = posts_table.query(
            KeyConditionExpression=Key("PostID").eq(post_id)
        )
    except ClientError as err:
        log(f"Error while fetching the post record: {err}")
        return {
            "statusCode": 500,
            "body": json.dumps({"run_id": run_id, "error_stage": "post_fetching"})
        }
    post_record = response["Items"][0]
    print(f"FETCHED RECORD: {post_record}")
    post_version = post_record["Version"]
    post_record["Version"] += 1
    post_record["CommentCount"] -= 1
    
    print(f"POSTING RECORD: {post_record}")
    
    # Attempt to write until the version matches
    while True:
        try:
            response = posts_table.put_item(
                Item=post_record,
                ConditionExpression=Attr("Version").eq(post_version)
            )
            print(f"WRITE RESPONSE: {response}")
        except ClientError as err:
            print("CLIENT ERROR:" + str(err))
            if err.response["Error"]["Code"] == 'ConditionalCheckFailedException':
                post_record["Version"] += 1
                continue
        break

    # Standard succesfl case
    return {
        "statusCode": 200,
        "body": json.dumps(f"Deleted comment {comment_id} for post {post_id}")
    }
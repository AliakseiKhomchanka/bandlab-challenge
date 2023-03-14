# TODO: Add proper image resizing and format conversion 
# (Pillow is having problems so far for unknown reasons)

import boto3
from io import BytesIO
import base64
import json
from time import time
from botocore.exceptions import ClientError


IMAGES_BUCKET = "akhomchanka-challenge-images"
POSTS_TABLE = "challenge_posts"

# Resource clients
s3 = boto3.resource("s3")
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
    images_bucket = s3.Bucket(IMAGES_BUCKET)
    posts_table = dynamodb.Table(POSTS_TABLE)
    # --------------------------------------------------------------------------
    
    # The run ID of the function will be used as the ID of the post
    post_id = run_id
    
    # Decode image contents from base64
    image_base64 = body.get("image_contents")
    if not image_base64:
        log("No image in the request body, aborting...")
        return {
            "statusCode": 400,
            "body": json.dumps({"run_id": run_id})
        }
    image_contents = base64.b64decode(image_base64)

    # Upload the original image to S3
    try:
        images_bucket.upload_fileobj(BytesIO(image_contents), post_id + ".jpg")
    except ClientError as err:
        log(f"Error while uploading the image: {err}")
        return {
            "statusCode": 500,
            "body": json.dumps({"run_id": run_id, "error_stage": "image_upload"})
        }

    # Add the post record to the DynamoDB table
    # We don't need to explicitly store the image path in the record because it 
    # already has the same name as the post ID so we always know where to look later
    record = {
        "PostID": post_id,
        "Timestamp": int(time()),
        "Author": body["author"],
        "CommentCount": 0,
        "Body": body["body"],
        "Status": "ok",
        "Version": 0
    }
    try:
        posts_table.put_item(Item=record)
    except ClientError as err:
        log(f"Error while updating the posts table: {err}")
        return {
            "statusCode": 500,
            "body": json.dumps({"run_id": run_id, "error_stage": "posts_table_update"})
        }

    # Default successful case
    return {
        "statusCode": 201,
        "body": json.dumps(record)
    }

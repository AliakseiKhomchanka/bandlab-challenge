# Imagegram

This repository is my implementation of the BandLab challenge for the backend of a system that handles posts with images and comments to said posts.

The entiry system is implemented using serverless managed services in AWS and can be deployed via a CloudFormation template.

## **Task**

### User stories

- As a user, I should be able to create posts with images (1 post - 1 image)

- As a user, I should be able to set a text caption when I create a post

- As a user, I should be able to comment on a post

- As a user, I should be able to delete a comment (created by me) from a post

- As a user, I should be able to get the list of all posts along with the last 2 comments
to each post

---

### Functional Requirements

- RESTful Web API (JSON)

- Maximum image size - 100MB

- Allowed image formats: .png, .jpg, .bmp.

- Save uploaded images in the original format

- Convert uploaded images to .jpg format and resize to 600x600

- Serve images only in .jpg format

- Posts should be sorted by the number of comments (desc)

- Retrieve posts via a cursor-based pagination

---

### Non-functional requirements

- Maximum response time for any API call except uploading image files - 50 ms

- Minimum throughput handled by the system - 100 RPS

- Users have a slow and unstable internet connection

---

### Usage forecast

- 1k uploaded images per 1h

- 100k new comments per 1h

---

## **System structure**

As mentioned, the system utilizes some serverless services in AWS, mainly:

- **AWS Lambda** for running the logic behing API endpoints
- **Simple Storage Service (S3)** for storing images and Lambda function deployment packages
- **DynamoDB** for storing post and comment data
- **API Gateway** for defining and managing the API
- **CloudFormation** for defining and provisioning the entire infrastructure

Below is the exact diagram of the system:

![System diagram](https://else-youtube.s3.eu-central-1.amazonaws.com/system-diagram.drawio.png)
[System diagram](https://else-youtube.s3.eu-central-1.amazonaws.com/system-diagram.drawio.png)

The HTTP API defined in the API Gateway service has three paths with four methods corresponding to user stories:

| Method + Path | Purpose |
|---|---|
| GET /posts | Get all posts |
| POST /posts | Add a new post |
| POST /posts/{post_id}/comments | Add a new coment to a specific post |
| DELETE /posts/{post_id}/comments/{comment_id} | Delete a specific comment on a specific post |

Each Method+Path combination has an integration with a corresponding Lambda function. Functions, on turn, have integrations with posts and comments tables in DynamoDB and images bucket in S3, access to all of which is granted by an execution role created specifically for those functions. Exact nature of interaction between Lambda functions and tables/buckets can be seen in the function code and corresponding comments.

### **Data models**

There are two tables, one for posts and another one for comments. They have the following data models:

**Posts**

| Key | Type |
|---|---|
| PostID (partition key) | String |
| Timestamp (sort key) | Number |
| Author | String |
| Body | String |
| CommentCount | Number |
| Status | String |
| Version | Integer |

There is also a Global Secondary Index in the posts table with the partition key Status and the sort key CommentCount. It is used to get posts sorted by teh comment count in descending order.

**Comments**

| Key | Type |
|---|---|
| CommentID (partition key) | String |
| Timestamp (sort key) | Number |
| Author | String |
| Body | String |
| PostID | Number |

There is also a Global Secondary Index in the comments table with the partition key PostID and the sort key Timestamp. It is used to fetch comments for a post in chronological order.

NOTE: Defining a default sort key Timestamp in the table was a bad decision as now I need to fetch the comment record to get its timestamp before I can construct a full key to delete it instead of just referring to the CommentID and deleting it right away. I should have just left the sort key undefined (as it would be useless with CommentID field as the value of that field is unique for each comment) but by the time I've realized that it would take too long to rewire and test everything again within the allocated time frame. So it is not the optimal solution but I'm aware of the fact.

## **API DOCUMENTATION**

All POST requests require the "Content-Type: application/json" header.

No authentication is required.

Actions:
---
---
<mark style="background-color: #c9eb9b"> **GET** </mark>    **/posts**

Fetches all posts currently present in the database

**Query parameters:**

<mark style="background-color: #b4b7e0"> limit </mark>   integer *OPTIONAL*

Limits the number or posts returned in a single request.

<mark style="background-color: #b4b7e0"> nextPage </mark>   string *OPTIONAL*

The pagination pointer (url encoded), corresponds to the nextPage field returned in the body of a previous response.

<details>
<summary>Example response</summary>

```
{
    "nextPage": 
        {
        "PostID": "2283c3aa-0ae1-42ff-a364-bfd954333469", 
        "Timestamp": 1678671432, 
        "Status": "ok", "CommentCount": 1
        }, 
    "posts": [
        {
            "PostID": "83df3a6c-1487-41c5-815a-faef8c154816", 
            "Timestamp": 1678661515,
            "Author": "Myself", 
            "Version": 15, 
            "Status": "ok", 
            "CommentCount": 2, 
            "Body": "This is my post, ha-ha la-la and all that", 
            "LastComments": [
                {
                    "PostID": "83df3a6c-1487-41c5-815a-faef8c154816", 
                    "Timestamp": 1678661923, 
                    "Author": "Myself", 
                    "CommentID": "93394863-b6ed-4a3c-9115-8eb7a0ce261c", 
                    "Body": "Comment innit"}, 
                {
                    "PostID": "83df3a6c-1487-41c5-815a-faef8c154816", 
                    "Timestamp": 1678661922,
                    "Author": "Myself", 
                    "CommentID": "f43303b3-77b8-44ac-ab3f-66385af76ca8",
                    "Body": "Comment innit"}
            ], 
            "Image": "12345"
        }, 
        {
            "PostID": "07afad02-d79e-434c-b38e-982c5886da8d", 
            "Timestamp": 1678661514, 
            "Author": "Myself", 
            "Version": 0, 
            "Status": "ok", 
            "CommentCount": 0, 
            "Body": "This is my post, ha-ha la-la and all that", 
            "LastComments": [], 
            "Image": "12345"
        }, 
        {
            "PostID": "0b74b25a-0329-4779-936d-9a4407ab08ab", 
            "Timestamp": 1678661516, 
            "Author": "Myself", 
            "Version": 0, 
            "Status": "ok", 
            "CommentCount": 0, 
            "Body": "This is my post, ha-ha la-la and all that", 
            "LastComments": [], 
            "Image": "12345"
        }
    ]
}
```
</details>

NOTE: The image in each post is returned in base64 format 

---
<mark style="background-color: #e3ca5d"> **POST** </mark>    **/posts**

Adds a new post to the database

**Body parameters:**

<mark style="background-color: #b4b7e0"> author </mark>   string *REQUIRED*

Author of the post.

<mark style="background-color: #b4b7e0"> body </mark>   string *REQUIRED*

Text of the intended post.

<mark style="background-color: #b4b7e0"> image_contents </mark>   string *REQUIRED*

Image contents in base64 format.

<details>
<summary>Example response</summary>

```
{
    "PostID": "09c89c06-796d-4692-a137-1cab7621ead4", 
    "Timestamp": 1678807963, 
    "Author": "Myself", 
    "CommentCount": 0, 
    "Body": "This is my post, ha-ha la-la and all that", 
    "Status": "ok", 
    "Version": 0
}

```
</details>

---
<mark style="background-color: #e3ca5d"> **POST** </mark>    **/posts/{post_id}/comments**

Adds a new comment to the specified post

**Path parameters:**

<mark style="background-color: #b4b7e0"> post_id </mark>   string *REQUIRED*

ID of the post for which the comment is added.

**Body parameters:**

<mark style="background-color: #b4b7e0"> author </mark>   string *REQUIRED*

Author of the post.

<mark style="background-color: #b4b7e0"> body </mark>   string *REQUIRED*

Text of the intended comment.

<details>
<summary>Example response</summary>

```
{
    "CommentID": "c1248f52-0bbb-4412-b709-6fc3ab697a83", 
    "Timestamp": 1678808559, 
    "Author": "Myself", 
    "Body": "Comment innit", 
    "PostID": "09c89c06-796d-4692-a137-1cab7621ead4"
}

```
</details>

---
<mark style="background-color: #f09673"> **DELETE** </mark>    **/posts/{post_id}/comments/{comment_id}**

Deletes the specified comment from the specified post

**Path parameters:**

<mark style="background-color: #b4b7e0"> post_id </mark>   string *REQUIRED*

ID of the post to which the comment belongs.

<mark style="background-color: #b4b7e0"> comment_id </mark>   string *REQUIRED*

ID of the comment to be deleted.

<details>
<summary>Example response</summary>

```
"Deleted comment c1248f52-0bbb-4412-b709-6fc3ab697a83 for post 09c89c06-796d-4692-a137-1cab7621ead4"
```
</details>

---

## **System design reasoning**

In this section I describe some of the design decisions I took and reasons for them.

### Usage of AWS in general

AWS, out of all public cloud providers is, in my opinion, the most well-documented and consistent, which makes developing with it much faster and smoother. From experience, while platforms like Azure have more or less feature parity with AWS for the purposes of this particular project, they are more cumbersome to work with and sometimes unstable in their behavior.

### Usage of AWS Lambda

Lambda is a managed service where I can just upload my code, set a couple of parameters like memory limit, timeout etc. - and natively integrate my functions with other AWS services like DynamoDB, S3 and API Gateway and provide access for them in a couple of clicks with predefined execution roles. With Lambda it is also very easy to isolate separate runs of the code, much easier compared to options like running pods in Kubernetes, for example.

It also has convenient log collection via CloudWatch out of the box.

### Usage of DynamoDB

While AWS also has its RDS service, I don't require any of its relational features and would rather use a simpler fully managed solution like DynamoDB that also natively integrates with my Lambda code via the boto3 library for Python.

### Index in the posts table

As you may notice, there is the "Status" field in the posts table that is always set to "ok". This is done for the index that looks at ALL posts with the sorting key of CommentCount. The only way I'm aware of to make that possible is having a large partition with all elements. Looking at the performance limits of partitions in DynamoDB and the intended write frequency of the system, it is well within those limits with plenty of room to scale up. While it intuitively feels somewhat clunky, such an approach is not unheard of and can sometimes even be seen in official AWS guides on DynamoDB.

## **Things missing in the current state of the repository**

### Unit tests

Function code in this case doesn't do much aside from forwarding inputs to databases/buckets or querying said databases/buckets without doing much transformation on the data itself aside from simple type casting or incrementing/decrementing values. At this scale there isn't really anything that warrants unit testing. Testing calls of individual calls or different resource functions in boto3 would pretty much devolve into defining a bunch of mocks and checking that those mocks always return correct values (which they always will due to the very nature of mocks).

On the other hand, some automated end-to-end tests to confirm that the system works as a whole would be beneficial. User stories here can be used to define those end-to-end tests.

### Image processing

I have attempted to use Pillow for resizing and converting image formats, but for yet unclear reason Pillow seems to corrupt images when working with them in-memory. The mechanism works if temporary files are used instead of BytesIO objects, but that's a clunkier solution. None of the documentation and discussions regarding Pillow have helped so far so I have left that part out for now and just upload the original image without conversion to not go too far out of the recommended time frame for the challenge. Image size check is included in this section as well.

### Input schema checks

The current setup doesn't check whether incoming requests follow a specified schema, that fell outside of the intended development time frame.

### A simpler pagination pointer

Right now, the program returns the entire object that DynamoDB uses as a pointer. We can store that object in a separate table and just return its hash to the user for simplicity on their end. When they supply it in the request for the next page - we can fetch the object itself and supply it to DynamoDB.

## **What needs to be done before production**

There are some crucial improvements that need to be made before this project woudl be ready for proper production stage.

### Take care of the remaining functional requirements

Some crucial functionality like image resizing is missing so that needs to be added.

### Make the CloudFormation template more general

The current template for CloudFormation has hardcoded names, instead it should be using parameters so that it's able to be deployed into different environments in the same account, like dev, test and production.

### Make deployment of CloudFormation stacks automated

As fast and convenient as CloudFormation is, ths deployment process should be automated for more smooth integration process.

### Use environment variables in Lambda

Right now, names of resources like DynamoDB tables and S3 buckets are hard-coded in the function code. This is inconvenient if we want to deploy several stacks from the same template. Rather, functions should get names of relevant resources from environment variables, which in turn would be set with parameters in the CloudFormation template.

### Authentication

Seeing as the system is supposed to support different users, it would probably make sense to implement authentication to make sure users can only manipulate their posts, their comments and maybe others'comments on their posts.

### Adjust permissions

Current permissions on Lambda functions allow full access to S3, CloudWatch and DynamoDB. This is undesirable and should be switched to utilize the minimum privilege principle. I have left it out for now to not dig through all the settings in IAM, but in anything close to an actual dev/prod environment this should be set properly.

## **Deployment**

To deploy the stack, use the template.yml file in the root of the repository. All the .zip deployment archives for Lambda functions are in a public S3 bucket and should be available for download. If for some reason they are not - the code for functions is also in the repository.
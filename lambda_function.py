#!/usr/bin/python3 

from __future__ import print_function
from datetime import datetime as dt

import boto3
import argparse
import re
import os

client = boto3.client('ecr')

REGION = None
DRYRUN = None
IMAGES_TO_KEEP = None
IGNORE_TAGS_REGEX = None
DELETE_FROM_DATE = None

def initialize():
    global DELETE_FROM_DATE
    global DRYRUN
    global REGION
    global IGNORE_TAGS_REGEX

# Setting Region to None during initialization  
    REGION = os.environ.get('REGION', "ap-south-1")
# Setting Region to False during initialization  
    DRYRUN = os.environ.get('DRYRUN', "false").lower()
    if DRYRUN == "false":
        DRYRUN = False
    else:
        DRYRUN = True
# Setting for regex value to None by default and waiting for input
    IGNORE_TAGS_REGEX = os.environ.get('IGNORE_TAGS_REGEX', "^$")
    
# Setting the default date to None    
    DELETE_FROM_DATE = os.environ.get('DELETE_FROM_DATE', "None")

def lambda_handler(event, context):
    initialize()
    describe_deleteimages(REGION)    

def describe_deleteimages(regionname):
    repositories = []       #name of repositories present in the specific zone
    imageDigest = []        #storing the sha sum of the images
    repos = []              #name of repositories present
    images = []             #name of images that are present in the repo
    details = []            #details include the images details as a whole while executing aws ecr describe-images --respository repo_name
    pushDate= []            #date on which the images were pushed on ECR Repository
    digest=[]
    imageInfo = []  #initializing with null value to store info of images such imagepushed date, image tags and image digest
    
    print("Discovering images in " + regionname)
    ecr_client = boto3.client('ecr', region_name=regionname)
    
    describe_repo_paginator = ecr_client.get_paginator('describe_repositories')
    list_image_paginator = ecr_client.get_paginator('list_images')
    describe_image_paginator = ecr_client.get_paginator('describe_images')
    
    ignore_tags_regex = re.compile(IGNORE_TAGS_REGEX)
    
    for response_listrepopaginator in describe_repo_paginator.paginate():
        for repo in response_listrepopaginator['repositories']:
            repositories.append(repo)

    for repo in repositories:
        repos.append(repo)

    for repository in repositories:
        strTime = []    #initializing with null value to store date in string format for comparision
        print("\033[0;32m ----------------------------------------------------------------------------------------------------------")
        print("\033[0;32m Starting with repository: " + repository['repositoryUri'])
        print("\033[0;32m ----------------------------------------------------------------------------------------------------------")
        for response_describeimagepaginator in describe_image_paginator.paginate(registryId = repository['registryId'], repositoryName = repository['repositoryName']):
            for detail in response_describeimagepaginator['imageDetails']:
                details.append(detail)
                for image in detail['imageTags']:
                    digest.append(detail['imageDigest'])                    
                    images.append(image)
                    pushDate.append(detail['imagePushedAt'])
                    
        for i in pushDate:
            strTime.append(i.strftime("%Y-%m-%d"))
            
        for total in range(len(strTime)):
            if "latest" not in images[total] and ignore_tags_regex.search(images[total]) is None:
                if not {'imageDigest': digest[total]} in imageDigest: 
                    if DELETE_FROM_DATE >= strTime[total]:
                        print("\33[34m Adding ...")
                        imageDigest.append({"imageDigest": digest[total]})
                        imageInfo.append({'imagePushedAt': pushDate[total],'imageTags': images[total], "imageDigest": details[total]})
                    else:
                        print("Repo Name:", repository['repositoryName'],"Image Digest: ", imageDigest, "len of imageDigest: ", len(imageDigest))
                        print("\33[34m Skipping ...")
                    
        print("\033[0;32m #-----Image URLs that are marked for deletion-----#", repository['repositoryName'])
        if len(imageDigest) <= 0:
            print("\033[1;30;47m NOTE:", "\033[0;31m There are no images older than mentioned date")
        #for repo in repos:
        for lrow in imageInfo:
            print("\033[0;31m -{} - {} - {}".format(repository['repositoryUri'], lrow['imageTags'], lrow['imagePushedAt']))

        delete_image(imageDigest, repository, ecr_client)
    
def delete_image(imageDigest, repository, ecr_client):
    for delete in range(len(imageDigest)):
        if not DRYRUN:
            delete_response = ecr_client.batch_delete_image(
                    registryId = repository['registryId'],
                    repositoryName = repository['repositoryName'],
                    imageIds = imageDigest
            )
            print("\033[0;33m Deleing images: ",  delete_response)

if __name__ == '__main__':
    REQUEST = {"None": "None"}    
    PARSER = argparse.ArgumentParser(description='Deletes stale ECR images')    
# Help options for dry run    
    PARSER.add_argument('-dryrun', help='prints the images to be deleted without deleting them', default='true', action='store', dest='dryrun')    
# Help option for image delete date    
    PARSER.add_argument('-date', help='date from which the image is to be deleted', default=dt.now, action='store', dest='deletefromdate')
    PARSER.add_argument('-region', help='region where the ECR repository is present', default=None, action='store', dest='region')    
    PARSER.add_argument('-ignoretagsregex', help='tag names to ignore', default="^$", action='store', dest='ignoretagsregex')    
    ARGS = PARSER.parse_args()    
    if ARGS.region:
        os.environ["REGION"] = ARGS.region
    else:
        os.environ["REGION"] = "None"
# Information for Dry Run argument
    os.environ["DRYRUN"] = ARGS.dryrun.lower()    
# Information for Date argument    
    os.environ["DELETE_FROM_DATE"] = ARGS.deletefromdate
    os.environ["IGNORE_TAGS_REGEX"] = ARGS.ignoretagsregex    
    lambda_handler(REQUEST, None)

It is available in us-west-2
Yes, it can be 8000

CPU/Memory combinations are available
Yes, you can do plain environment variables. It lets you type key value pairs while using the service in the console.
All those IAM roles are able to be created
Min 0 is allowed
Will have to see what the url looks like after creation.
It can be /health
Scenario 1: If you updated the Image Tag (Recommended)
The "Application URL" looked like this: https://ag-2b97a70421a545179ae8859a6d13cd5e.ecs.us-west-2.on.aws/  After I created it
If your new image has a new unique tag (e.g., a version number or a git commit SHA), you must point your service's task definition to the new image URI and update the service

aws ecs update-service \
    --cluster <your-cluster-name> \
    --service <your-service-name> \
    --task-definition <your-new-task-definition-arn-or-family>


Scenario 2: If you reused the same tag (e.g., latest)

If you pushed a new container image to ECR but kept the exact same tag (like latest), Amazon ECS won't automatically notice the change because the image URI string remains identical.

aws ecs update-service \
    --cluster <your-cluster-name> \
    --service <your-service-name> \
    --force-new-deployment

Hopefully that explains it. :D



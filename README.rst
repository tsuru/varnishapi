Varnish service API for tsuru PaaS
==================================

.. image:: https://travis-ci.org/globocom/varnishapi.png?branch=master
   :target: https://travis-ci.org/globocom/varnishapi
Deploying the API
-----------------

First, let's create an app in tsuru, from the project root, execute the following:

.. highlight: bash

::

    % tsuru app-create varnishapi python
    % git remote add tsuru git@remote.sbrubles.com # the returned remote ;)
    % git push tsuru master

The push will return an error telling you that you can't push code before the
app unit is up, wait until your unit is in service, you can check with:

    $> tsuru app-list

When you get an output like this you can proceed to push.

    +------------------+-------------------------+------------------------------------------------------------------+
    | Application      | Units State Summary     | Address                                                          |
    +------------------+-------------------------+------------------------------------------------------------------+
    | your-app         | 1 of 1 units in-service | your-app.sa-east-1.elb.amazonaws.com                             |
    +------------------+-------------------------+------------------------------------------------------------------+

Now if you access our app endpoint at "/" (you can check with `tsuru app-info`
cmd) you should get a 404, which is right, since our api does not respond
through this url.

Alright, let's configure our application, it'll need to talk with EC2 api, and
it does so by using environment variables. Here's what you need:

    $> tsuru env-set EC2_ACCESS_KEY=your-access-key EC2_SECRET_KEY=your-secret-key

We'll need to pass the ami we just generated to run when a user requests a
service creation, let's set what ami we're gonna use:

    $> tsuru env-set AMI_ID=your-ami-id

If you are running this on a VPC, you'll also need to tell the api in which
subnet it will spawn the service's vms for the applications:

    $> tsuru env-set SUBNET_ID=your-subnet-id

Every service instance has an elastic load balancing in front of it, which by
default, is configured to `internet-facing`, which means you can access it
publicly, if you don't want this behavior, set the `ELB_SCHEME` environment
variable to `internal`.

The api also needs a ssh key in order to comunicate with the service instances'
vms, let's generate it:

    $> tsuru run 'ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa'

Let's set our database path and create it:

    $> tsuru env-set DB_PATH=/home/application/varnishapi.db
    $> tsuru run "sqlite3 /home/application/varnishapi.db < /home/application/current/database.sql"

We're done with our api! Let's create the service in tsuru.


Creating the Service
--------------------

First you'll have to change the `manifest.yaml` file located at the project
root of our application.  Change the key `endpoint:production` to the
application address, your yaml should look like this:

    id: varnish
    endpoint:
        production: varnishapi-endpoint.com
        test: localhost:8000

Let's ignore the `test` endpoint for now.  Now let's tell tsuru it needs to
registrate a new service, from the project root run:

    $> crane create manifest.yaml

Aaaand we're done!

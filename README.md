Varnish service API for tsuru PaaS
==================================


Required Tools
--------------

We're going to need tsuru's command line to deploy our application, we're also gonna need the service specific client, `crane`,
check the [installation guide](http://docs.tsuru.io/en/latest/install/client.html) for more details.

We are also using wget on the varnish server that we setup, but it's probably already there.


Pre Configuration
-----------------

This api uses a ami with varnish installed and with some basic configurations, such as listen in port 80.
You will need to build that image, I suggest booting a amazon instance, install and configure everything and then generate
an ami from the instance.

You'll find varnish installation steps for ubuntu (a shell, actually) in the `setup` directory with the configuration files.
Let's install it (you'll need root access):

    $> wget -O - https://raw.github.com/globocom/varnishapi/master/setup/install.sh | bash

Okay, now let's configure it to listen on 80:

    $> wget -O varnish https://raw.github.com/globocom/varnishapi/master/setup/varnish
    $> sudo mv /etc/default/varnish /etc/default/varnish.old
    $> sudo mv varnish /etc/default/varnish

Restart it so the configurations can take effect:

    $> sudo service varnish restart

All you'll need now is to generate an ami from that instance, our api is going to make use of it.

Pice of cake! The next step is to deploy our api.


Deploying the API
-----------------

First, let's create an app in tsuru, from the project root, execute the following:

    $> tsuru app-create varnishapi python
    $> git remote add tsuru git@remote.sbrubles.com # the returned remote ;)
    $> git push tsuru master

Now if you access our app endpoint at "/" (you can check with `tsuru app-info` cmd) you should get a 404, which is right,
since our api does not respond through this url.

Alright, let's configure our application, it'll need to talk with EC2 api, and it does so by using environment variables. Here's what you need:

    $> tsuru env-set EC2_ACCESS_KEY=your-access-key EC2_SECRET_KEY=your-secret-key

We'll need to pass the ami we just generated to run when a user requests a service creation, let's set what ami we're gonna use:

    $> tsuru env-set AMI_ID=your-ami-id

If you are running this on a VPC (which it is meant for), you'll also need to tell the api in which subnet it will spawn the service's vms for the applications:

    $> tsuru env-set SUBNET_ID=your-subnet-id

Every service instance has an elastic load balancing in front of it, which by default, is configured to `internet-facing`, which means you can access it publicly,
if you don't want this behavior, set the `ELB_SCHEME` environment variable to `internal`.

The api also needs a ssh key in order to comunicate with the service instances' vms, let's generate it:

    $> tsuru run 'ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa'

Lets set our database path and create it:

    $> tsuru env-set DB_PATH=/home/application/varnishapi.db
    $> tsuru run "sqlite3 /home/application/varnishapi.db < /home/application/current/database.sql"

We're done with our api! Let's create the service in tsuru.


Creating the Service
--------------------

First you'll have to change the `manifest.yaml` file located at the project root of our application.
Change the key `endpoint:production` to the application address, your yaml should look like this:

    id: varnish
    endpoint:
        production: varnishapi-endpoint.com
        test: localhost:8000

Let's ignore the `test` endpoint for now.
Now let's tell tsuru it needs to registrate a new service, from the project root run:

    $> crane create manifest.yaml

Aaaand we're done!

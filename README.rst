Setup
=====

Install the necessary dependencies, e.g. in a virtualenv:

::

    pip install -r requirements.txt

Register the app as a personal use script on reddit and create a
praw.ini with the necessary information:

::

    [gamethread]
    client_id = 
    client_secret = 
    user_agent = gamethreads/1.0
    username = 
    password = 

Alternatively you can generate a refresh\_token, e.g. using the `example
script <https://praw.readthedocs.io/en/latest/tutorials/refresh_token.html#refresh-token>`__
from the PRAW docs. In the future this should probably be an automatic
part of this code.

# FindMy404

We have many web sites in Internet with some ugly errors like "Page not found"
or something like this.
This script allows you to scan your web site recursively and find all 404 / 500
error pages before it will be found by your customers.


HowTo Use
---------

1) Install requirements:
```
    pip install -r requirements.txt
    sudo apt-get install xvfb
```
2) Install geckodriver
3) Edit configuration file ```server.conf```
4) Run the script:
```
    ./get404.py
```
5) Check log file results.txt


ToDo List
---------

1) Add Authentication methods
2) Rewrite multi-threading with Scrappy pool
3) Add W3C validation for pages

Analogs
-------

You can also try Xenu. It is doing the same staff but it can't use
authentication for web sites and perform W3C validation.

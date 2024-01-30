# CAN-TcpCanStream
PeCAN service to receive TCP request from router and execute associated action.

## Set-up the service
Once the repository has been cloned on the home dorectory `/home/YOURUSERNAME/`, do:
* Copy bash script in ~ directory `sudo cp TcpCanStrean.sh ~` 
* Modify `YOURUSERNAME` by your actual username in the file with `sudo nano TcpCanStream.sh`
* Change access rights with sudo `chmod +x TcpCanStream.sh`
* Copy service file from repository to system directory `sudo cp TcpCanStrean.service /etc/systemd/system/`
* Modify `YOURUSERNAME` by your actual username in the file with `sudo nano TcpCanStream.service`
* Reload daemon with `sudo systemctl daemon-reload`
* Enable service with `sudo systemctl enable TcpCanStream.service`
* Start service with `sudo systemctl start TcpCanStream.service`
* Check status with `systemctl status TcpCanStream.service`

From now on, the service TcpCanStream will start running at the device boot. 

## Handled requests:
The TcpCanStream service is listening on port tcp 5558 to receive requests and reply back on tcp port 5559:
* `identify`: to send back its hostname to the router.
* `start`: to start recording CAN messages from the CAN-HAT and send them back to the router in a data stream.
* `stop`: to stop recording and create log files.
* `clean`: to clean all the log files (used after the router copied those files with a sftp get request).

## Functionment:
To perform this service, the zmq package is used, with a SUB socket to receice the requests (send from the router with a PUB socket) and a DEALER socker to send response back (to ROUTER socket from the router). A while loop is running to listen permanently and if a reauest is received and recognized in the list previously mentionned, the action triggered will be performed in parallel in a thread until the action is over or it gets interrupted but another order. 
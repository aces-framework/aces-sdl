FROM nexus.ocr.cr14.net:8003/ocr-base-deployment-image

RUN apt update && apt upgrade -y
RUN apt install ranger-server -y

CMD ["/var/opt/ranger/bin/ranger", "/etc/opt/ranger/ranger/config.yml"]

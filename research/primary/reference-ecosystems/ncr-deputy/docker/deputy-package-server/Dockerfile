FROM nexus.ocr.cr14.net:8003/ocr-base-deployment-image

RUN apt update && apt upgrade -y
RUN apt install deputy-package-server default-libmysqlclient-dev -y
 
CMD ["/var/opt/deputy/bin/deputy-package-server", "/etc/opt/deputy/deputy-package-server/config.yml"]

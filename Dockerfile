FROM registry.access.redhat.com/ubi8/ubi
RUN yum -y install httpd && yum clean all
ADD edge.ks /var/www/html/
ADD repo /var/www/html/repo/
EXPOSE 80
CMD ["/usr/sbin/httpd", "-D", "FOREGROUND"]

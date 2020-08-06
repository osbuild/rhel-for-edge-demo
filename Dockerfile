FROM registry.access.redhat.com/ubi8/ubi
RUN yum -y install httpd && yum clean all
ADD edge.ks /var/www/html/
ARG commit=commit.tar
ADD $commit /var/www/html/
EXPOSE 80
CMD ["/usr/sbin/httpd", "-D", "FOREGROUND"]

FROM registry.access.redhat.com/ubi8/ubi
ARG commit=commit.tar
RUN yum -y install httpd && yum clean all
ADD edge.ks /var/www/html/
ADD $commit /var/www/html/
EXPOSE 80
CMD ["/usr/sbin/httpd", "-D", "FOREGROUND"]

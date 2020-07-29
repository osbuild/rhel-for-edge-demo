FROM registry.access.redhat.com/ubi8/ubi
RUN yum -y install httpd && yum clean all
EXPOSE 80
CMD ["/usr/sbin/httpd", "-D", "FOREGROUND"]

Vagrant.configure("2") do |config|
    config.vagrant.plugins= ["vagrant-env"]
    config.vm.box = "generic/rhel8"
    config.env.enable
    config.vm.provision :shell, path: "bootstrap.sh", 
         args: "#{ENV['USER']} #{ENV['PASS']}"
end
# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "chef/centos-6.5"
  config.vm.network :forwarded_port, guest: 5000, host: 5000
  config.vm.provision "shell", path: "vagrant.sh"

  # config.vm.provider :virtualbox do |vb|
  #   vb.customize ["modifyvm", :id, "--memory", "1024"]
  # end
end

# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

box = {
    :box => "ubuntu/trusty64",
    :hostname => "psdash-dev",
    :ram => 256
}

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = box[:box]
  config.vm.hostname = "%s" % box[:hostname]
  config.vm.provider "virtualbox" do |v|
    v.customize ["modifyvm", :id, "--memory", box[:ram]]
    v.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
  end
  config.vm.network :forwarded_port, guest: 5000, host: 5000
  config.vm.provision "shell", path: "vagrant.sh"
end

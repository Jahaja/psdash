# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

boxes = [
  {
    :name => "ubuntu-1204",
    :box => "opscode-ubuntu-12.04",
    :url => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_ubuntu-12.04_chef-provisionerless.box",
    :cpu => "50",
    :ram => "256",
    :ip => '10.0.1.10'
  },
  {
    :name => "debian-720",
    :box => "opscode-debian-7.2.0",
    :url => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_debian_7.2.0_chef-provisionerless.box",
    :cpu => "50",
    :ram => "256",
    :ip => '10.0.1.11'
  },
  {
    :name => "centos-6.5",
    :box => "chef/centos-6.5",
    :url => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_centos-6.5_chef-provisionerless.box",
    :cpu => "50",
    :ram => "256",
    :ip => '10.0.1.12'
  }
]

# let's use one box at a time, defaulting to CentOS 6.5
box = boxes[2]

require 'rbconfig'
include RbConfig

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
    config.vm.define box[:name] do |config|
      config.vm.box = box[:box]
      config.vm.box_url = box[:url]
      config.vm.hostname = "%s" % box[:name]

      config.vm.provider "virtualbox" do |v|
        v.customize ["modifyvm", :id, "--cpuexecutioncap", box[:cpu]]
        v.customize ["modifyvm", :id, "--memory", box[:ram]]
      end

      config.vm.network :private_network, ip: box[:ip]

      case CONFIG['host_os']
        when /mswin|windows|mingw32/i
          config.vm.provision "shell", path: "vagrant.sh"
        else
          config.vm.provision :ansible do |ansible|
            ansible.playbook = "psdash.yml"
            ansible.limit = "%s" % box[:name]
            # ansible.verbose = "vvvv"
            ansible.host_key_checking = false
          end
      end
    end
end

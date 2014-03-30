# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

boxes = [
  {:name => "ubuntu-1204", :box => "opscode-ubuntu-12.04", :url => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_ubuntu-12.04_chef-provisionerless.box", :cpu => "50", :ram => "256", :ip => '10.0.1.10'},
  {:name => "debian-720",  :box => "opscode-debian-7.2.0", :url => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_debian_7.2.0_chef-provisionerless.box", :cpu => "50", :ram => "256", :ip => '10.0.1.11'},
  {:name => "centos-6.5",  :box => "chef/centos-6.5",      :url => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_centos-6.5_chef-provisionerless.box", :cpu => "50", :ram => "256", :ip => '10.0.1.12'},
]

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  boxes.each do |box|
    config.vm.define box[:name] do |vms|
      vms.vm.box = box[:box]
      vms.vm.box_url = box[:url]
      vms.vm.hostname = "%s" % box[:name]

      vms.vm.provider "virtualbox" do |v|
        v.customize ["modifyvm", :id, "--cpuexecutioncap", box[:cpu]]
        v.customize ["modifyvm", :id, "--memory", box[:ram]]
      end

      vms.vm.network :private_network, ip: box[:ip]

      vms.vm.provision :ansible do |ansible|
        ansible.playbook = "psdash.yml"
        ansible.limit = "%s" % box[:name]
        # ansible.verbose = "vvvv"
        ansible.host_key_checking = false
      end
    end
  end
end

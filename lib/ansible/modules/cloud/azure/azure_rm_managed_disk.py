#!/usr/bin/python
#
# Copyright (c) 2017 Bruno Medina Bolanos Cacho <bruno.medina@microsoft.com>
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: azure_rm_managed_disk

version_added: "2.4"

short_description: Manage Azure Manage Disks

description:
    - Create, update and delete an Azure Managed Disk

options:
    resource_group:
        description:
            - Name of a resource group where the managed disk exists or will be created.
        required: true
    name:
        description:
            - Name of the managed disk.
        required: true
    state:
        description:
            - Assert the state of the managed disk. Use C(present) to create or update a managed disk and C(absent) to delete a managed disk.
        default: present
        choices:
            - absent
            - present
    location:
        description:
            - Valid Azure location. Defaults to location of the resource group.
    storage_account_type:
        description:
            - "Type of storage for the managed disk."
            - "If not specified, the disk is created as C(Standard_LRS)."
            - "C(Standard_LRS) is for Standard HDD."
            - "C(StandardSSD_LRS) (added in 2.8) is for Standard SSD."
            - "C(Premium_LRS) is for Premium SSD."
            - "C(UltraSSD_LRS) (added in 2.8) is for Ultra SSD, which is in preview mode, and only available on select instance types."
            - "See https://docs.microsoft.com/en-us/azure/virtual-machines/windows/disks-types for more information about disk types."
        choices:
            - Standard_LRS
            - StandardSSD_LRS
            - Premium_LRS
            - UltraSSD_LRS
    create_option:
        description:
            - "Allowed values: empty, import, copy.
            - C(import) from a VHD file in I(source_uri) and C(copy) from previous managed disk I(source_uri)."
        choices:
            - empty
            - import
            - copy
    source_uri:
        description:
            - URI to a valid VHD file to be used or the resource ID of the managed disk to copy.
        aliases:
            - source_resource_uri
    os_type:
        description:
            - "Type of Operating System: C(linux) or C(windows)."
            - "Used when I(create_option) is either C(copy) or C(import) and the source is an OS disk."
            - "If omitted during creation, no value is set."
            - "If omitted during an update, no change is made."
            - "Once set, this value cannot be cleared."
        choices:
            - linux
            - windows
    disk_size_gb:
        description:
            - "Size in GB of the managed disk to be created."
            - "If I(create_option) is C(copy) then the value must be greater than or equal to the source's size."
    managed_by:
        description:
            - Name of an existing virtual machine with which the disk is or will be associated, this VM should be in the same resource group.
            - To detach a disk from a vm, explicitly set to ''.
            - If this option is unset, the value will not be changed.
        version_added: 2.5
    tags:
        description:
            - Tags to assign to the managed disk.

extends_documentation_fragment:
    - azure
    - azure_tags
author:
    - "Bruno Medina (@brusMX)"
'''

EXAMPLES = '''
    - name: Create managed disk
      azure_rm_managed_disk:
        name: mymanageddisk
        location: eastus
        resource_group: myResourceGroup
        disk_size_gb: 4

    - name: Create managed operating system disk from page blob
      azure_rm_managed_disk:
        name: mymanageddisk
        location: eastus2
        resource_group: myResourceGroup
        create_option: import
        source_uri: https://storageaccountname.blob.core.windows.net/containername/blob-name.vhd
        os_type: windows
        storage_account_type: Premium_LRS

    - name: Mount the managed disk to VM
      azure_rm_managed_disk:
        name: mymanageddisk
        location: eastus
        resource_group: myResourceGroup
        disk_size_gb: 4
        managed_by: testvm001

    - name: Unmount the managed disk to VM
      azure_rm_managed_disk:
        name: mymanageddisk
        location: eastus
        resource_group: myResourceGroup
        disk_size_gb: 4

    - name: Delete managed disk
      azure_rm_manage_disk:
        name: mymanageddisk
        location: eastus
        resource_group: myResourceGroup
        state: absent
'''

RETURN = '''
id:
    description: The managed disk resource ID.
    returned: always
    type: dict
state:
    description: Current state of the managed disk
    returned: always
    type: dict
changed:
    description: Whether or not the resource has changed
    returned: always
    type: bool
'''

import re


from ansible.module_utils.azure_rm_common import AzureRMModuleBase
try:
    from msrestazure.tools import parse_resource_id
    from msrestazure.azure_exceptions import CloudError
except ImportError:
    # This is handled in azure_rm_common
    pass


# duplicated in azure_rm_managed_disk_facts
def managed_disk_to_dict(managed_disk):
    create_data = managed_disk.creation_data
    return dict(
        id=managed_disk.id,
        name=managed_disk.name,
        location=managed_disk.location,
        tags=managed_disk.tags,
        create_option=create_data.create_option.lower(),
        source_uri=create_data.source_uri or create_data.source_resource_id,
        disk_size_gb=managed_disk.disk_size_gb,
        os_type=managed_disk.os_type.lower() if managed_disk.os_type else None,
        storage_account_type=managed_disk.sku.name if managed_disk.sku else None,
        managed_by=managed_disk.managed_by
    )


class AzureRMManagedDisk(AzureRMModuleBase):
    """Configuration class for an Azure RM Managed Disk resource"""

    def __init__(self):
        self.module_arg_spec = dict(
            resource_group=dict(
                type='str',
                required=True
            ),
            name=dict(
                type='str',
                required=True
            ),
            state=dict(
                type='str',
                default='present',
                choices=['present', 'absent']
            ),
            location=dict(
                type='str'
            ),
            storage_account_type=dict(
                type='str',
                choices=['Standard_LRS', 'StandardSSD_LRS', 'Premium_LRS', 'UltraSSD_LRS']
            ),
            create_option=dict(
                type='str',
                choices=['empty', 'import', 'copy']
            ),
            source_uri=dict(
                type='str',
                aliases=['source_resource_uri']
            ),
            os_type=dict(
                type='str',
                choices=['linux', 'windows']
            ),
            disk_size_gb=dict(
                type='int'
            ),
            managed_by=dict(
                type='str'
            )
        )
        required_if = [
            ('create_option', 'import', ['source_uri']),
            ('create_option', 'copy', ['source_uri']),
            ('create_option', 'empty', ['disk_size_gb'])
        ]
        self.results = dict(
            changed=False,
            state=dict())

        self.resource_group = None
        self.name = None
        self.location = None
        self.storage_account_type = None
        self.create_option = None
        self.source_uri = None
        self.os_type = None
        self.disk_size_gb = None
        self.tags = None
        self.managed_by = None
        super(AzureRMManagedDisk, self).__init__(
            derived_arg_spec=self.module_arg_spec,
            required_if=required_if,
            supports_check_mode=True,
            supports_tags=True)

    def exec_module(self, **kwargs):
        """Main module execution method"""
        for key in list(self.module_arg_spec.keys()) + ['tags']:
            setattr(self, key, kwargs[key])

        result = None
        changed = False

        resource_group = self.get_resource_group(self.resource_group)
        if not self.location:
            self.location = resource_group.location

        disk_instance = self.get_managed_disk()
        result = disk_instance

        # need create or update
        if self.state == 'present':
            parameter = self.generate_managed_disk_property()
            if not disk_instance or self.is_different(disk_instance, parameter):
                changed = True
                if not self.check_mode:
                    result = self.create_or_update_managed_disk(parameter)
                else:
                    result = True

        # unmount from the old virtual machine and mount to the new virtual machine
        if self.managed_by or self.managed_by == '':
            vm_name = parse_resource_id(disk_instance.get('managed_by', '')).get('name') if disk_instance else None
            vm_name = vm_name or ''
            if self.managed_by != vm_name:
                changed = True
                if not self.check_mode:
                    if vm_name:
                        self.detach(vm_name, result)
                    if self.managed_by:
                        self.attach(self.managed_by, result)
                    result = self.get_managed_disk()

        if self.state == 'absent' and disk_instance:
            changed = True
            if not self.check_mode:
                self.delete_managed_disk()
            result = True

        self.results['changed'] = changed
        self.results['state'] = result
        return self.results

    def attach(self, vm_name, disk):
        vm = self._get_vm(vm_name)
        # find the lun
        luns = ([d.lun for d in vm.storage_profile.data_disks]
                if vm.storage_profile.data_disks else [])
        lun = max(luns) + 1 if luns else 0

        # prepare the data disk
        params = self.compute_models.ManagedDiskParameters(id=disk.get('id'), storage_account_type=disk.get('storage_account_type'))
        data_disk = self.compute_models.DataDisk(lun=lun, create_option=self.compute_models.DiskCreateOptionTypes.attach, managed_disk=params)
        vm.storage_profile.data_disks.append(data_disk)
        self._update_vm(vm_name, vm)

    def detach(self, vm_name, disk):
        vm = self._get_vm(vm_name)
        leftovers = [d for d in vm.storage_profile.data_disks if d.name.lower() != disk.get('name').lower()]
        if len(vm.storage_profile.data_disks) == len(leftovers):
            self.fail("No disk with the name '{0}' was found".format(disk.get('name')))
        vm.storage_profile.data_disks = leftovers
        self._update_vm(vm_name, vm)

    def _update_vm(self, name, params):
        try:
            poller = self.compute_client.virtual_machines.create_or_update(self.resource_group, name, params)
            self.get_poller_result(poller)
        except Exception as exc:
            self.fail("Error updating virtual machine {0} - {1}".format(name, str(exc)))

    def _get_vm(self, name):
        try:
            return self.compute_client.virtual_machines.get(self.resource_group, name, expand='instanceview')
        except Exception as exc:
            self.fail("Error getting virtual machine {0} - {1}".format(name, str(exc)))

    def generate_managed_disk_property(self):
        # TODO: Add support for EncryptionSettings, DiskIOPSReadWrite, DiskMBpsReadWrite, Zones
        disk_params = {}
        creation_data = {}
        disk_params['location'] = self.location
        disk_params['tags'] = self.tags
        if self.storage_account_type:
            storage_account_type = self.compute_models.DiskSku(name=self.storage_account_type)
            disk_params['sku'] = storage_account_type
        disk_params['disk_size_gb'] = self.disk_size_gb
        creation_data['create_option'] = self.compute_models.DiskCreateOption.empty
        if self.create_option == 'import':
            creation_data['create_option'] = self.compute_models.DiskCreateOption.import_enum
            creation_data['source_uri'] = self.source_uri
        elif self.create_option == 'copy':
            creation_data['create_option'] = self.compute_models.DiskCreateOption.copy
            creation_data['source_resource_id'] = self.source_uri
        if self.os_type:
            typecon = {
                'linux': self.compute_models.OperatingSystemTypes.linux,
                'windows': self.compute_models.OperatingSystemTypes.windows
            }
            disk_params['os_type'] = typecon[self.os_type]
        else:
            disk_params['os_type'] = None
        disk_params['creation_data'] = creation_data
        return disk_params

    def create_or_update_managed_disk(self, parameter):
        try:
            poller = self.compute_client.disks.create_or_update(
                self.resource_group,
                self.name,
                parameter)
            aux = self.get_poller_result(poller)
            return managed_disk_to_dict(aux)
        except CloudError as e:
            self.fail("Error creating the managed disk: {0}".format(str(e)))

    # This method accounts for the difference in structure between the
    # Azure retrieved disk and the parameters for the new disk to be created.
    def is_different(self, found_disk, new_disk):
        resp = False
        if new_disk.get('disk_size_gb'):
            if not found_disk['disk_size_gb'] == new_disk['disk_size_gb']:
                resp = True
        if new_disk.get('os_type'):
            if not found_disk['os_type'] == new_disk['os_type']:
                resp = True
        if new_disk.get('sku'):
            if not found_disk['storage_account_type'] == new_disk['sku'].name:
                resp = True
        # Check how to implement tags
        if new_disk.get('tags') is not None:
            if not found_disk['tags'] == new_disk['tags']:
                resp = True
        return resp

    def delete_managed_disk(self):
        try:
            poller = self.compute_client.disks.delete(
                self.resource_group,
                self.name)
            return self.get_poller_result(poller)
        except CloudError as e:
            self.fail("Error deleting the managed disk: {0}".format(str(e)))

    def get_managed_disk(self):
        try:
            resp = self.compute_client.disks.get(
                self.resource_group,
                self.name)
            return managed_disk_to_dict(resp)
        except CloudError as e:
            self.log('Did not find managed disk')


def main():
    """Main execution"""
    AzureRMManagedDisk()


if __name__ == '__main__':
    main()

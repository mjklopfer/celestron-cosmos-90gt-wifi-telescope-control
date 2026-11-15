"""Host-independent fixtures for interface enumeration and neighbor parsing."""
import ipaddress
import socket
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import psutil
from network_info import network_interfaces, parse_neighbors, connected_lans, directly_attached


class InterfaceInventoryTests(unittest.TestCase):
    def fixture(self):
        return {'Ethernet': [NS(family=socket.AF_INET, address='192.168.50.2', netmask='255.255.255.0'),
                             NS(family=psutil.AF_LINK, address='02-00-00-00-00-01')],
                'Wi-Fi': [NS(family=socket.AF_INET, address='1.2.3.10', netmask='255.255.255.0')],
                'USB Ethernet': [],
                'Loopback': [NS(family=socket.AF_INET, address='127.0.0.1', netmask='255.0.0.0')]}

    def test_os_native_names_addresses_masks_and_inactive_interfaces(self):
        with patch('network_info.psutil.net_if_addrs', return_value=self.fixture()), \
             patch('network_info.psutil.net_if_stats', return_value={
                 'Ethernet': NS(isup=True), 'Wi-Fi': NS(isup=True), 'USB Ethernet': NS(isup=False)}):
            rows = network_interfaces()
        self.assertEqual(rows[0]['interface'], 'Ethernet')
        self.assertEqual(rows[0]['netmask'], '255.255.255.0')
        self.assertEqual(rows[2]['state'], 'inactive')
        self.assertEqual(rows[2]['ip'], '—')
        self.assertEqual(rows[3]['state'], 'loopback')

    def test_neighbor_formats_windows_linux_and_bsd(self):
        cases = [(' 192.168.50.100   00-06-66-11-22-33  dynamic', ''),
                 ('192.168.50.100 dev eth0 lladdr 00:06:66:11:22:33 REACHABLE', 'eth0'),
                 ('? (192.168.50.100) at 0:6:66:11:22:33 on en0 ifscope [ethernet]', 'en0')]
        for text, interface in cases:
            with self.subTest(text=text):
                row = parse_neighbors(text)[0]
                self.assertEqual(row['ip'], '192.168.50.100')
                self.assertEqual(row['mac'], '00:06:66:11:22:33')
                self.assertEqual(row['interface'], interface)
        self.assertEqual(parse_neighbors('192.168.50.100 dev eth0 FAILED'), [])

    def test_discovery_filters_large_public_loopback_and_inactive_subnets(self):
        rows = [{'interface': str(i), 'ip': ip, 'netmask': mask, 'state': state}
                for i, (ip, mask, state) in enumerate([
                    ('192.168.50.2', '255.255.255.0', 'active'),
                    ('1.2.3.10', '255.255.255.0', 'active'),
                    ('10.0.0.2', '255.0.0.0', 'active'),
                    ('8.8.8.8', '255.255.255.0', 'active'),
                    ('127.0.0.1', '255.255.255.0', 'active'),
                    ('192.168.51.2', '255.255.255.0', 'inactive')])]
        with patch('network_info.network_interfaces', return_value=rows):
            results = connected_lans()
        self.assertEqual([r[2] for r in results], [ipaddress.ip_network('192.168.50.0/24'), ipaddress.ip_network('1.2.3.0/24')])

    def test_direct_route_requires_matching_active_interface_and_mask(self):
        rows = [{'ip': '1.2.3.10', 'netmask': '255.255.255.0', 'state': 'active'}]
        with patch('network_info.network_interfaces', return_value=rows), \
             patch('network_info.route_source_address', return_value='1.2.3.10'):
            self.assertTrue(directly_attached('1.2.3.4'))
        with patch('network_info.network_interfaces', return_value=rows), \
             patch('network_info.route_source_address', return_value='192.168.50.2'):
            self.assertFalse(directly_attached('1.2.3.4'))

from setuptools import find_packages, setup

package_name = 'battery_status'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/battery_status.launch.py']),
    ],
    install_requires=['setuptools', 'pyserial'],
    zip_safe=True,
    maintainer='shijaz',
    maintainer_email='shijaz@todo.todo',
    description='Battery status publisher for ESP32 exoskeleton.',
    license='TODO: License declaration',
    extras_require={
        'test': ['pytest'],
    },
    entry_points={
        'console_scripts': [
            'battery_status_node = battery_status.battery_status_node:main',
        ],
    },
)

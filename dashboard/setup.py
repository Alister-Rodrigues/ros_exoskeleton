from setuptools import find_packages, setup

package_name = 'dashboard'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/pyqt6_launch.py']),
    ],
    install_requires=['setuptools', 'PyQt6'],
    zip_safe=True,
    maintainer='alister',
    maintainer_email='alister@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'pyqt6_node = dashboard.pyqt6_node:main'
        ],
    },
)

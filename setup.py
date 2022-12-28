from setuptools import setup

setup(
    name='iot_devices',
    version='0.1dev',
    packages=['iot_devices',],
    license='MIT License',
    long_description=open('README.md').read(),
    dependencies = [
        "paho.mqtt",
        "urwid",
        "scullery",
        "yeelight",
        "colorzero"
    ]
)

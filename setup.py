from setuptools import setup, find_packages

setup(
    name='iot_devices',
    version='0.1.13',
    author="Daniel Dunn",
    author_email="dannydunn@eternityforest.com",
    packages=find_packages(),
    package_data={'': ["*.json"]},
    license='MIT',
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/EternityForest/iot_devices",
    entry_points={
        'console_scripts': [
            'tui-dash = iot_devices.tui_dash:main',
        ],
    },
    dependencies=[
        "paho.mqtt",
        "urwid",
        "scullery",
        "yeelight",
        "colorzero"
    ]
)

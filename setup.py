from setuptools import setup, find_packages


setup(
    name='nimi',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    python_requires='>=3',
    install_requires=[
        'boto3>=1.4.4',
        'click>=6.7',
        'Jinja2>=2.9.6',
        'requests>=2.18.1',
        'terminaltables>=3.1.0'
    ],
    entry_points='''
        [console_scripts]
        nimi=nimi.cli:cli
        nimi-client=nimi.client:cli
    ''',
)
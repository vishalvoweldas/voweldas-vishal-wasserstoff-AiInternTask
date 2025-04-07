from setuptools import setup, find_packages

setup(
    name="email_processor",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'google-auth-oauthlib',
        'google-auth-httplib2',
        'google-api-python-client',
        'python-dotenv',
        'beautifulsoup4',
        'requests',
        'slack_sdk',
        'transformers',
        'tensorflow',
        'torch',
        'huggingface_hub'
    ]
) 
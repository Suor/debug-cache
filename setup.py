from setuptools import setup


setup(
    name='debug-cache',
    version='0.0.1',
    author='Alexander Schepanovski',
    author_email='suor.web@gmail.com',

    description='A way to speed up debugging and testing.',
    long_description=open('README.rst').read(),
    url='http://github.com/Suor/debug-cache',
    license='BSD',

    py_modules=['debug_cache'],
    install_requires=[
        'funcy>=1.2,<2.0',
        'termcolor',
        'py',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        # 'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        # 'Programming Language :: Python :: 3',
        # 'Programming Language :: Python :: 3.3',
        # 'Programming Language :: Python :: 3.4',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)

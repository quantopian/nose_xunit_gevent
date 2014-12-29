
import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()

requires = [
    'nose'
]


setup(name='nose_xunit_gevent',
      version='0.1',
      description='Xunit output when running gevented multiprocess tests using nose',
      long_description=README,
      classifiers=[
          "Development Status :: 3 - Alpha",
          "Intended Audience :: Developers",
          "License :: OSI Approved :: Apache License 2.0",
          "Operating System :: OS Independent",
          "Programming Language :: Python",
          "Topic :: Software Development :: Testing",
      ],
      license='Apache',
      author='Jonathan Kamens',
      author_email='jik@quantopian.com',
      url='',
      keywords='nosetest xunit multiprocessing',
      py_modules=['nose_xunit_gevent'],
      include_package_data=True,
      zip_safe=True,
      entry_points="""\
      [nose.plugins.0.10]
      xunitmp = nose_xunit_gevent:XunitGevent
      """,
      install_requires=requires)

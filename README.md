offswitch
=========
[![No Maintenance Intended](http://unmaintained.tech/badge.svg)](http://unmaintained.tech)
![Python version range](https://img.shields.io/badge/python-2.7%20|%203.4%20|%203.5%20|%203.6%20|%203.7%20|%203.8-blue.svg)
[![License](https://img.shields.io/badge/license-Apache--2.0%20OR%20MIT-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Destroy compute nodes.

## Usage

    $ python -m offswitch -h
    usage: __main__.py [-h] [-s STRATEGY]
    
    Destroy compute nodes
    
    optional arguments:
      -h, --help            show this help message and exit
      -s STRATEGY, --strategy STRATEGY
                            strategy file [strategy.sample.json]

## Roadmap

  - Glob removals, e.g.: `python -m offswitch -g /unclustered/any-cluster*`
  - Provider removals, e.g.: `python -m offswitch -p SOFTLAYER`
  - Improved success output and handling of provider errors

## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or <https://www.apache.org/licenses/LICENSE-2.0>)
- MIT license ([LICENSE-MIT](LICENSE-MIT) or <https://opensource.org/licenses/MIT>)

at your option.

### Contribution

Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in the work by you, as defined in the Apache-2.0 license, shall be
dual licensed as above, without any additional terms or conditions.

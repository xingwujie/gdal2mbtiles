import os
from shutil import rmtree
import unittest

from gdal2mbtiles.renderers import TouchRenderer
from gdal2mbtiles.storages import NestedFileStorage, SimpleFileStorage
from gdal2mbtiles.types import rgba
from gdal2mbtiles.utils import intmd5, NamedTemporaryDir, recursive_listdir
from gdal2mbtiles.vips import VImage


class TestSimpleFileStorage(unittest.TestCase):
    def setUp(self):
        self.tempdir = NamedTemporaryDir()
        self.outputdir = self.tempdir.__enter__()
        self.renderer = TouchRenderer(suffix='.png')
        self.storage = SimpleFileStorage(outputdir=self.outputdir,
                                         renderer=self.renderer,
                                         hasher=intmd5)

    def tearDown(self):
        self.tempdir.__exit__(None, None, None)

    def test_create(self):
        # Make a new directory if it doesn't exist
        os.rmdir(self.outputdir)
        storage = SimpleFileStorage(outputdir=self.outputdir,
                                    renderer=self.renderer)
        self.assertEqual(storage.outputdir, self.outputdir)
        self.assertTrue(os.path.isdir(self.outputdir))

        # Make a duplicate directory
        SimpleFileStorage(outputdir=self.outputdir,
                          renderer=self.renderer)
        self.assertTrue(os.path.isdir(self.outputdir))

    def test_filepath(self):
        self.assertEqual(self.storage.filepath(x=0, y=1, z=2,
                                               hashed=0xdeadbeef),
                         '2-0-1-deadbeef' + self.renderer.suffix)

    def test_get_hash(self):
        image = VImage.new_rgba(width=1, height=1,
                                ink=rgba(r=0, g=0, b=0, a=0))
        self.assertEqual(self.storage.get_hash(image=image),
                         long('f1d3ff8443297732862df21dc4e57262', base=16))

    def test_save(self):
        image = VImage.new_rgba(width=1, height=1,
                                ink=rgba(r=0, g=0, b=0, a=0))
        self.storage.save(x=0, y=1, z=2, image=image)
        self.storage.save(x=1, y=0, z=2, image=image)
        self.storage.waitall()
        self.assertEqual(set(os.listdir(self.outputdir)),
                         set([
                             '2-0-1-f1d3ff8443297732862df21dc4e57262.png',
                             '2-1-0-f1d3ff8443297732862df21dc4e57262.png'
                         ]))

        # Is this a real file?
        self.assertFalse(
            os.path.islink(os.path.join(
                self.outputdir, '2-0-1-f1d3ff8443297732862df21dc4e57262.png'
            ))
        )

        # Does the symlinking work?
        self.assertEqual(
            os.readlink(os.path.join(
                self.outputdir, '2-1-0-f1d3ff8443297732862df21dc4e57262.png'
            )),
            '2-0-1-f1d3ff8443297732862df21dc4e57262.png'
        )

    def test_symlink(self):
        # Same directory
        src = 'source'
        dst = 'destination'
        self.storage.symlink(src=src, dst=dst)
        self.assertEqual(os.listdir(self.outputdir),
                         [dst])
        self.assertEqual(os.readlink(os.path.join(self.outputdir, dst)),
                         src)

        # Subdirs
        subdir = os.path.join(self.outputdir, 'subdir')
        os.mkdir(subdir)
        self.storage.symlink(src=src, dst=os.path.join(subdir, dst))
        self.assertEqual(os.listdir(subdir),
                         [dst])
        self.assertEqual(os.readlink(os.path.join(subdir, dst)),
                         os.path.join(os.path.pardir, src))


class TestNestedFileStorage(unittest.TestCase):
    def setUp(self):
        self.tempdir = NamedTemporaryDir()
        self.outputdir = self.tempdir.__enter__()
        self.renderer = TouchRenderer(suffix='.png')
        self.storage = NestedFileStorage(outputdir=self.outputdir,
                                         renderer=self.renderer,
                                         hasher=intmd5)

    def tearDown(self):
        self.tempdir.__exit__(None, None, None)

    def test_create(self):
        # Make a new directory if it doesn't exist
        os.rmdir(self.outputdir)
        storage = NestedFileStorage(outputdir=self.outputdir,
                                    renderer=self.renderer)
        self.assertEqual(storage.outputdir, self.outputdir)
        self.assertTrue(os.path.isdir(self.outputdir))

        # Make a duplicate directory
        NestedFileStorage(outputdir=self.outputdir,
                          renderer=self.renderer)
        self.assertTrue(os.path.isdir(self.outputdir))

    def test_filepath(self):
        self.assertEqual(self.storage.filepath(x=0, y=1, z=2,
                                               hashed=0xdeadbeef),
                         '2/0/1' + self.renderer.suffix)

    def test_makedirs(self):
        # Cache should be empty
        self.assertFalse(self.storage.madedirs)

        self.storage.makedirs(x=0, y=1, z=2)
        self.assertEqual(set(recursive_listdir(self.outputdir)),
                         set(['2/',
                              '2/0/']))

        # Is cache populated?
        self.assertTrue(self.storage.madedirs[2][0])

        # Delete and readd without clearing cache
        rmtree(os.path.join(self.outputdir, '2'))
        self.assertEqual(os.listdir(self.outputdir), [])
        self.storage.makedirs(x=0, y=1, z=2)
        self.assertEqual(os.listdir(self.outputdir), [])

    def test_save(self):
        image = VImage.new_rgba(width=1, height=1,
                                ink=rgba(r=0, g=0, b=0, a=0))
        self.storage.save(x=0, y=1, z=2, image=image)
        self.storage.save(x=1, y=0, z=2, image=image)
        self.storage.save(x=1, y=0, z=3, image=image)
        self.storage.waitall()
        self.assertEqual(set(recursive_listdir(self.outputdir)),
                         set(['2/',
                              '2/0/',
                              '2/0/1.png',
                              '2/1/',
                              '2/1/0.png',
                              '3/',
                              '3/1/',
                              '3/1/0.png']))

        # Is this a real file?
        self.assertFalse(
            os.path.islink(os.path.join(self.outputdir, '2', '0', '1.png'))
        )

        # Does the symlinking work?
        self.assertEqual(
            os.readlink(os.path.join(self.outputdir, '2', '1', '0.png')),
            os.path.join(os.path.pardir, '0', '1.png')
        )
        self.assertEqual(
            os.readlink(os.path.join(self.outputdir, '3', '1', '0.png')),
            os.path.join(os.path.pardir, os.path.pardir, '2', '0', '1.png')
        )
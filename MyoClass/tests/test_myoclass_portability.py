"""Exercise real MyoClass project files with a deterministic inference stub.

Run: python -m unittest discover -s MyoClass/tests -v
Requires the normal MyoClass scientific Python dependencies, but no GPU/Cellpose.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
import tifffile as tiff

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = next(ROOT.glob('Downloads/MyoTools-Linux/MyoClass/MyoClass_v1.0.2.ipynb'), None)
if NOTEBOOK is None:
    NOTEBOOK = ROOT / 'MyoClass/MyoClass_v1.0.2.ipynb'


def load_core(path):
    namespace = {'__name__': 'myoclass_test'}
    notebook = json.loads(Path(path).read_text(encoding='utf-8'))
    with contextlib.redirect_stdout(io.StringIO()):
        for cell in notebook['cells'][:3]:
            exec(compile(''.join(cell['source']), str(path), 'exec'), namespace)
    return namespace


CORE = load_core(NOTEBOOK)
LEGACY_NOTEBOOK = ROOT / 'MyoClass/tests/fixtures/MyoClass_v1.0.1_core.json'
if not LEGACY_NOTEBOOK.is_file():
    LEGACY_NOTEBOOK = ROOT / 'MyoClass/MyoClass_v1.0.1.ipynb'
LEGACY = load_core(LEGACY_NOTEBOOK)


class ProjectPortabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.original = self.base / 'original'
        self.original.mkdir()
        self.images = self.original / 'images'
        self.masks = self.original / 'masks'
        for folder in (self.images / 'set', self.masks / 'set'):
            folder.mkdir(parents=True)
        self.reference = np.zeros((20, 20), dtype=np.uint16)
        self.reference[2:8, 2:8] = 1
        self.reference[11:17, 11:17] = 3
        raw = np.stack([np.arange(400).reshape(20, 20), np.ones((20, 20))]).astype(np.uint16)
        tiff.imwrite(self.images / 'set/section.tif', raw, metadata={'axes': 'CYX'}, photometric='minisblack')
        tiff.imwrite(self.masks / 'set/section_masks.tif', self.reference)
        self.model = self.original / 'model'
        self.model.write_bytes(b'test-model')
        self.settings = dict(input_dir=str(self.images), mask_dir=str(self.masks), model=str(self.model),
            output_dir=str(self.original / 'MyoClass_results'), recursive=True,
            channels=[{'index': 0, 'name': 'Automatic', 'mode': 'automatic'},
                      {'index': 1, 'name': 'Manual', 'mode': 'manual'},
                      {'index': 2, 'name': 'Inferred', 'mode': 'inferred'}],
            axes='auto', time=0, z=0, all_scenes=False, align_to_mask=False,
            mask_mode='none', edge_only=False, gaussian_sigma=0., scale_mode='fixed',
            fixed_scale=1., mask_strength=0., normalize_nonzero=False,
            diameter=20., flow_threshold=0.4, cellprob_threshold=0., min_size=0,
            batch_size=1, cellpose_normalize=True, overlap=0.5, force=False,
            pixel_size=1., preview_size=100, device='cpu', calibration='manual',
            csa_max=1000., csa_step=100., feret_max=100., feret_step=10.,
            compute_feret=False, exclude_border=False, area_min=0., area_max=0.,
            export_source='reviewed')
        self.calls = 0
        outer = self
        class Model:
            def eval(self, plane, **kwargs):
                outer.calls += 1
                return outer.reference.copy(), None, None
        self.factory = lambda settings, emit: Model()

    def make_project(self, legacy=False, reviewed=False):
        core = LEGACY if legacy else CORE
        result = core['run_automatic'](self.settings, model_factory=self.factory)
        self.assertEqual(result['successful'], 1, result)
        self.root = Path(self.settings['output_dir'])
        entry = core['available_entries'](self.root)[0]
        doc = core['ReviewDocument'](entry)
        doc.set_types('ch0', [0], 0)
        doc.set_types('ch1', [1], 1)
        doc.save(reviewed=reviewed)
        self.review_bytes = Path(entry['review_path']).read_bytes()
        self.meta_bytes = Path(entry['review_meta']).read_bytes()
        self.automatic_bytes = Path(entry['automatic_path']).read_bytes()
        self.original_entry = entry
        self.calls = 0
        return entry

    def move_project(self, preserve_times=False):
        destination = self.base / 'new-machine'
        shutil.copytree(self.original, destination, copy_function=shutil.copy2 if preserve_times else shutil.copy)
        shutil.rmtree(self.original)
        self.root = destination / 'MyoClass_results'
        for key, path in [('input_dir', destination / 'images'), ('mask_dir', destination / 'masks'),
                          ('model', destination / 'model'), ('output_dir', self.root)]:
            self.settings[key] = str(path)
        return CORE['load_portable_project'](self.root, self.settings)

    def assert_review_unchanged(self, state):
        entries = CORE['available_entries'](self.root)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(CORE['get_review_state'](entry), state)
        self.assertEqual(Path(entry['review_path']).read_bytes(), self.review_bytes)
        self.assertEqual(Path(entry['review_meta']).read_bytes(), self.meta_bytes)
        self.assertEqual(Path(entry['automatic_path']).read_bytes(), self.automatic_bytes)
        doc = CORE['ReviewDocument'](entry)
        self.assertEqual(list(doc.frame.ch0), [0, 1])
        self.assertEqual(list(doc.frame.ch1), [0, 1])
        self.assertEqual(list(doc.frame.ch2), [1, 0])
        session = json.loads((self.root / 'review_session.json').read_text())
        self.assertEqual(session['entries'][0]['review_path'], entry['review_path'])
        return entry

    def test_new_draft_survives_copy_with_new_timestamps_and_reuses_inference(self):
        self.make_project()
        self.move_project()
        self.assert_review_unchanged('Draft')
        result = CORE['run_automatic'](self.settings, model_factory=self.factory)
        self.assertEqual(result['successful'], 1)
        self.assertEqual(result['reused'], 1)
        self.assertEqual(self.calls, 0)
        self.assert_review_unchanged('Draft')

    def test_reviewed_project_exports_after_moving_without_original_inputs(self):
        self.make_project(reviewed=True)
        self.move_project()
        shutil.rmtree(self.root.parent / 'images')
        shutil.rmtree(self.root.parent / 'masks')
        (self.root.parent / 'model').unlink()
        CORE['load_portable_project'](self.root, {'output_dir': str(self.root)})
        self.assert_review_unchanged('Reviewed')
        result = CORE['export_measurements'](self.settings)
        self.assertTrue(result)
        self.assertEqual(self.calls, 0)

    def test_legacy_draft_migrates_without_editing_reviews(self):
        self.make_project(legacy=True)
        _, warnings = self.move_project()
        self.assertTrue(any('Legacy' in text for text in warnings))
        self.assert_review_unchanged('Draft')
        self.assertTrue(list((self.root / 'Log/Backups').glob('project_before_relocation_*.json')))

    def test_legacy_reviewed_cache_reuses_when_original_metadata_matches(self):
        self.make_project(legacy=True, reviewed=True)
        self.move_project(preserve_times=True)
        self.assert_review_unchanged('Reviewed')
        result = CORE['run_automatic'](self.settings, model_factory=self.factory)
        self.assertEqual(result['reused'], 1)
        self.assertEqual(self.calls, 0)
        self.assert_review_unchanged('Reviewed')

    def test_changed_content_is_rejected_even_with_same_size_and_mtime(self):
        self.make_project()
        self.move_project()
        entry = self.assert_review_unchanged('Draft')
        path = Path(entry['prepared_paths']['ch0'])
        info = path.stat()
        contents = bytearray(path.read_bytes())
        contents[-1] ^= 1
        path.write_bytes(contents)
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        self.assertFalse(CORE['valid_entry'](entry))
        self.assertEqual(Path(entry['review_path']).read_bytes(), self.review_bytes)

    def test_parameter_change_invalidates_review_without_overwriting_edits(self):
        self.make_project()
        self.move_project()
        self.settings['overlap'] = 0.9
        result = CORE['run_automatic'](self.settings, model_factory=self.factory)
        self.assertEqual(result['successful'], 1)
        entry = CORE['available_entries'](self.root)[0]
        self.assertEqual(CORE['get_review_state'](entry), 'Stale review')
        self.assertEqual(Path(entry['review_path']).read_bytes(), self.review_bytes)

    def test_changed_model_requires_inference(self):
        self.make_project()
        self.move_project()
        Path(self.settings['model']).write_bytes(b'new--model')
        result = CORE['run_automatic'](self.settings, model_factory=self.factory)
        self.assertEqual(result['successful'], 1)
        self.assertEqual(self.calls, 1)

    def test_missing_prepared_file_does_not_recreate_or_reset_review(self):
        self.make_project()
        self.move_project()
        entry = CORE['available_entries'](self.root)[0]
        Path(entry['prepared_paths']['ch0']).unlink()
        CORE['load_portable_project'](self.root, self.settings)
        self.assertEqual(CORE['available_entries'](self.root), [])
        self.assertEqual(Path(entry['review_path']).read_bytes(), self.review_bytes)

    def test_windows_saved_paths_and_legacy_image_identity_are_preserved(self):
        self.make_project(legacy=True)
        manifest = self.root / 'Log/project.json'
        project = json.loads(manifest.read_text())
        old_id = project['active_ids'][0]
        new_id = old_id + '_legacy'
        for path in list(self.root.rglob('*')):
            if path.is_file() and old_id in path.name:
                path.rename(path.with_name(path.name.replace(old_id, new_id)))
        text = json.dumps(project).replace(old_id, new_id)
        project = json.loads(text)
        def windows_paths(value):
            if isinstance(value, dict): return {key: windows_paths(item) for key, item in value.items()}
            if isinstance(value, list): return [windows_paths(item) for item in value]
            if isinstance(value, str): return value.replace(str(self.original), 'C:/old/computer').replace('/', '\\') if ('/' in value and (value.startswith(str(self.original)) or value == 'set/section.tif')) else value
            return value
        project = windows_paths(project)
        manifest.write_text(json.dumps(project))
        # Metadata signature strings belong to the pre-move automatic mapping;
        # renaming an image identity does not change the review workbook itself.
        self.move_project()
        entry = self.assert_review_unchanged('Draft')
        self.assertEqual(entry['image_id'], new_id)
        result = CORE['run_automatic'](self.settings, model_factory=self.factory)
        self.assertEqual(result['successful'], 1)
        self.assertEqual(CORE['read_project'](self.root)['active_ids'], [new_id])

    def test_repeated_load_is_idempotent(self):
        self.make_project()
        self.move_project()
        manifest = (self.root / 'Log/project.json').read_bytes()
        CORE['load_portable_project'](self.root, self.settings)
        self.assertEqual((self.root / 'Log/project.json').read_bytes(), manifest)

    def test_legacy_review_opens_without_any_original_inputs(self):
        self.make_project(legacy=True, reviewed=True)
        self.move_project()
        for folder in ('images', 'masks'):
            shutil.rmtree(self.root.parent / folder)
        (self.root.parent / 'model').unlink()
        CORE['load_portable_project'](self.root, {'output_dir': str(self.root)})
        self.assert_review_unchanged('Reviewed')
        self.assertEqual(self.calls, 0)

    def test_stale_review_is_never_revalidated_by_loading(self):
        self.make_project(legacy=True)
        meta_path = Path(self.original_entry['review_meta'])
        meta = json.loads(meta_path.read_text())
        meta['automatic_signature'] = 'a-previous-classification'
        meta_path.write_text(json.dumps(meta))
        self.meta_bytes = meta_path.read_bytes()
        self.move_project()
        entry = CORE['available_entries'](self.root)[0]
        self.assertEqual(CORE['get_review_state'](entry), 'Stale review')
        self.assertEqual(Path(entry['review_meta']).read_bytes(), self.meta_bytes)
        self.assertEqual(json.loads((self.root / 'review_session.json').read_text())['entries'], [])

    def test_load_widget_keeps_selected_new_paths_and_restores_parameters(self):
        self.make_project(legacy=True)
        self.move_project()
        namespace = dict(CORE)
        notebook = json.loads(NOTEBOOK.read_text())
        with contextlib.redirect_stdout(io.StringIO()):
            exec(''.join(notebook['cells'][3]['source']), namespace)
            source = ''.join(notebook['cells'][4]['source']).split('myoclass_app=MyoClassApp()')[0]
            exec(source, namespace)
            app = namespace['MyoClassApp']()
            app.load_existing(self.settings)
        self.assertTrue(os.path.samefile(app.input_chooser.selected, self.settings['input_dir']))
        self.assertTrue(os.path.samefile(app.mask_chooser.selected, self.settings['mask_dir']))
        self.assertTrue(os.path.samefile(app.model_chooser.selected, self.settings['model']))
        self.assertTrue(os.path.samefile(app.output_path.value, self.root))
        self.assertEqual(app.overlap.value, self.settings['overlap'])
        self.assertEqual(len(app.review_image.options), 1)
        self.assertIn('Draft', app.review_image.options[0][0])
        self.assertEqual(self.calls, 0)

    def test_relocation_rejects_parent_traversal(self):
        with self.assertRaises(ValueError):
            CORE['relocated_path']('/old/results/Review/../../other.xlsx', '/old/results', self.base)


if __name__ == '__main__':
    unittest.main()

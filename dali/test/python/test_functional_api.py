import nvidia.dali.fn as fn
from nvidia.dali.pipeline import Pipeline
import nvidia.dali.types as types
import numpy as np
from test_utils import compare_pipelines
from test_utils import check_output_pattern
from nose.tools import assert_raises

def _test_fn_rotate(device):
    pipe = Pipeline(batch_size = 1, num_threads = 1, device_id = 0)

    image = np.array([
        [1, 2,  3,  4],
        [5, 6,  7,  8],
        [9, 10, 11, 12]], dtype=np.uint8)[:,:,np.newaxis]
    batch = [image]

    input = fn.external_source([batch], layout = "HWC")
    rotated = fn.rotate(input.gpu() if device == "gpu" else input,
                        angle = 90)
    pipe.set_outputs(rotated)

    pipe.build()
    outs = pipe.run()
    out = outs[0] if device == "cpu" else outs[0].as_cpu()
    arr = out.at(0)
    ref = np.array([
        [4, 8, 12],
        [3, 7, 11],
        [2, 6, 10],
        [1, 5, 9]])[:,:,np.newaxis]
    assert(np.array_equal(arr, ref))

def test_set_outputs():
    data = [[[np.random.rand(1, 3, 2)], [np.random.rand(1, 4, 5)]]]
    pipe = Pipeline(batch_size = 1, num_threads = 1, device_id = None)
    pipe.set_outputs(fn.external_source(data, num_outputs = 2, cycle = 'quiet'))
    assert_raises(TypeError, pipe.build)

def test_set_outputs_err_msg_unpack():
    data = [[[np.random.rand(1, 3, 2)], [np.random.rand(1, 4, 5)]]]
    pipe = Pipeline(batch_size = 1, num_threads = 1, device_id = None)
    pipe.set_outputs(fn.external_source(data, num_outputs = 2, cycle = 'quiet'))
    pattern = 'Illegal pipeline output type. The output 0 contains a nested `DataNode`. ' + \
              'Missing list/tuple expansion (*) is the likely cause.'
    try:
        pipe.build()
    except TypeError as e:
        assert(pattern == e.__str__())

def test_set_outputs_err_msg_random_type():
    pipe = Pipeline(batch_size = 1, num_threads = 1, device_id = None)
    pipe.set_outputs("test")
    pattern = "Illegal output type. The output 0 is a `<class 'str'>`. Allowed types are " + \
              "``DataNode`` and types convertible to `types.Constant` (numerical constants, " + \
              "1D lists/tuple of numbers and ND arrays)."
    try:
        pipe.build()
    except TypeError as e:
        assert(pattern == e.__str__())

def test_fn_rotate():
    for device in ["cpu", "gpu"]:
        yield _test_fn_rotate, device

def test_fn_python_function():
    pipe = Pipeline(1, 1, 0, exec_pipelined = False, exec_async = False)

    batch1 = [np.array([1,2,3])]
    batch2 = [np.array([2,3,4])]
    # we need a context, because we use an operator with potential side-effects (python_function)
    with pipe:
        src = fn.external_source([batch1, batch2])
        out = fn.python_function(src, function = lambda x: x+1)
        pipe.set_outputs(out)
    pipe.build()

    assert(np.array_equal(pipe.run()[0].at(0), batch1[0] + 1))
    assert(np.array_equal(pipe.run()[0].at(0), batch2[0] + 1))

def test_fn_multiple_input_sets():
    pipe = Pipeline(batch_size = 1, num_threads = 1, device_id = 0)

    image1 = np.array([
        [1, 2,  3,  4],
        [5, 6,  7,  8],
        [9, 10, 11, 12]], dtype=np.uint8)[:,:,np.newaxis]
    image2 = np.array([
        [10, 20],
        [30, 40],
        [50, 60]], dtype=np.uint8)[:,:,np.newaxis]
    batches = [[image1], [image2]]

    inputs = fn.external_source(lambda: batches, 2, layout = "HWC")
    rotated = fn.rotate(inputs, angle = 90)
    pipe.set_outputs(*rotated)

    pipe.build()
    outs = pipe.run()
    arr1 = outs[0].at(0)
    arr2 = outs[1].at(0)
    ref1 = np.array([
        [4, 8, 12],
        [3, 7, 11],
        [2, 6, 10],
        [1, 5, 9]])[:,:,np.newaxis]
    ref2 = np.array([
        [20, 40, 60],
        [10, 30, 50]], dtype=np.uint8)[:,:,np.newaxis]
    assert(np.array_equal(arr1, ref1))
    assert(np.array_equal(arr2, ref2))


def test_scalar_constant():
    pipe = Pipeline(batch_size = 1, num_threads = 1, device_id = 0)

    image1 = np.array([
        [1, 2,  3,  4],
        [5, 6,  7,  8],
        [9, 10, 11, 12]], dtype=np.uint8)[:,:,np.newaxis]
    image2 = np.array([
        [10, 20],
        [30, 40],
        [50, 60]], dtype=np.uint8)[:,:,np.newaxis]
    batches = [[image1], [image2]]

    inputs = fn.external_source(lambda: batches, 2, layout = "HWC")
    rotated = fn.rotate(inputs, angle = types.ScalarConstant(90))
    pipe.set_outputs(*rotated, types.ScalarConstant(90))

    pipe.build()
    outs = pipe.run()
    arr1 = outs[0].at(0)
    arr2 = outs[1].at(0)
    arr3 = outs[2].at(0)
    ref1 = np.array([
        [4, 8, 12],
        [3, 7, 11],
        [2, 6, 10],
        [1, 5, 9]])[:,:,np.newaxis]
    ref2 = np.array([
        [20, 40, 60],
        [10, 30, 50]], dtype=np.uint8)[:,:,np.newaxis]
    ref3 = np.array(90)
    assert(np.array_equal(arr1, ref1))
    assert(np.array_equal(arr2, ref2))
    assert(np.array_equal(arr3, ref3))

def test_to_snake_case_impl():
    fn_name_tests = [
        ('Test', 'test'),
        ('OneTwo', 'one_two'),
        ('TestXYZ', 'test_xyz'),
        ('testX', 'test_x'),
        ('TestXx', 'test_xx'),
        ('testXX', 'test_xx'),
        ('OneXYZTwo', 'one_xyz_two'),
        ('MFCC', 'mfcc'),
        ('RandomBBoxCrop', 'random_bbox_crop'),
        ('STFT_CPU', 'stft_cpu'),
        ('DOUBLE__UNDERSCORE', 'double__underscore'),
        ('double__underscore', 'double__underscore'),
        ('XYZ1ABC', 'xyz1abc'),
        ('XYZ1abc', 'xyz1abc'),
        ('trailing__', 'trailing__'),
        ('TRAILING__', 'trailing__'),
        ('Caffe2Reader', 'caffe2_reader'),
        ('COCOReader', 'coco_reader'),
        ('DLTensorPythonFunction', 'dl_tensor_python_function'),
        ('TFRecordReader', 'tfrecord_reader'),
    ]

    for inp, out in fn_name_tests:
        assert fn._to_snake_case(inp) == out, f"{fn._to_snake_case(inp)} != {out}"

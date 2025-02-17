// Copyright (c) 2018, NVIDIA CORPORATION. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#ifndef DALI_KERNELS_CONTEXT_H_
#define DALI_KERNELS_CONTEXT_H_

#include <cuda_runtime_api.h>
#include <utility>
#include <tuple>
#include <vector>
#include <algorithm>
#include <type_traits>
#include "dali/core/tensor_view.h"
#include "dali/kernels/alloc_type.h"

namespace dali {
namespace kernels {

template <typename ComputeBackend>
struct Context {};

template <>
struct Context<ComputeGPU> {
  cudaStream_t stream = 0;
};

class Scratchpad;

template <typename... Collections>
std::tuple<std::remove_cv_t<element_t<Collections>>*...>
ToContiguousHostMem(Scratchpad &scratchpad, const Collections &... c);

template <typename... Collections>
std::tuple<std::remove_cv_t<element_t<Collections>>*...>
ToContiguousGPUMem(Scratchpad &scratchpad, cudaStream_t stream, const Collections &... c);

/**
 * @brief Interface for kernels to obtain auxiliary working memory
 */
class Scratchpad {
 public:
  /**
   * @brief Allocates `bytes` bytes of memory in `alloc_type`, with specified `alignment`
   */
  virtual void *Alloc(AllocType alloc_type, size_t bytes, size_t alignment) = 0;

  /**
   * @brief Allocates storage for a Tensor of elements `T` and given `shape`
   *        in the memory of type `alloc_type`.
   */
  template <AllocType alloc_type, typename T, int dim>
  TensorView<AllocBackend<alloc_type>, T, dim> AllocTensor(TensorShape<dim> shape) {
    return { Allocate<T>(alloc_type, volume(shape)), std::move(shape) };
  }

  /**
   * @brief Allocates storage for a TensorList of elements `T` and given `shape`
   *        in the memory of type `alloc_type`.
   */
  template <AllocType alloc_type, typename T, int dim>
  TensorListView<AllocBackend<alloc_type>, T, dim>
  AllocTensorList(const std::vector<TensorShape<dim>> &shape) {
    return AllocTensorList<alloc_type, T, dim>(TensorListShape<dim>(shape));
  }

  /**
   * @brief Allocates storage for a TensorList of elements `T` and given `shape`
   *        in the memory of type `alloc_type`.
   */
  template <AllocType alloc_type, typename T, int dim>
  TensorListView<AllocBackend<alloc_type>, T, dim>
  AllocTensorList(TensorListShape<dim> shape) {
    T *data = Allocate<T>(alloc_type, shape.num_elements());
    TensorListView<AllocBackend<alloc_type>, T, dim> tlv(data, std::move(shape));
    return tlv;
  }

  /**
   * @brief Allocates memory suitable for storing `count` items of type `T` in the
   *        memory of type `alloc_type`.
   */
  template <typename T>
  T *Allocate(AllocType alloc_type, size_t count, size_t alignment = alignof(T)) {
    return reinterpret_cast<T*>(Alloc(alloc_type, count*sizeof(T), alignment));
  }

  template <typename Collection, typename T = std::remove_const_t<element_t<Collection>>>
  if_array_like<Collection, T*>
  ToGPU(cudaStream_t stream, const Collection &c) {
    T *ptr = Allocate<T>(AllocType::GPU, size(c));
    CUDA_CALL(cudaMemcpyAsync(ptr, &c[0], size(c) * sizeof(T), cudaMemcpyHostToDevice, stream));
    return ptr;
  }

  template <typename Collection, typename T = std::remove_const_t<element_t<Collection>>>
  if_iterable<Collection, T*>
  ToHost(const Collection &c) {
    T *ptr = Allocate<T>(AllocType::Host, size(c));
    std::copy(begin(c), end(c), ptr);
    return ptr;
  }

  template <typename Collection, typename T = std::remove_const_t<element_t<Collection>>>
  if_iterable<Collection, T*>
  ToPinned(const Collection &c) {
    T *ptr = Allocate<T>(AllocType::Pinned, size(c));
    std::copy(begin(c), end(c), ptr);
    return ptr;
  }

  template <typename Collection, typename T = std::remove_const_t<element_t<Collection>>>
  if_iterable<Collection, T*>
  ToUnified(const Collection &c) {
    T *ptr = Allocate<T>(AllocType::Unified, size(c));
    std::copy(begin(c), end(c), ptr);
    return ptr;
  }

  template <typename... Collections>
  auto ToContiguousHost(const Collections &...collections) {
    return ToContiguousHostMem(*this, collections...);
  }

  template <typename... Collections>
  auto ToContiguousGPU(cudaStream_t stream, const Collections &...collections) {
    return ToContiguousGPUMem(*this, stream, collections...);
  }

 protected:
  ~Scratchpad() = default;
};

using CPUContext = Context<ComputeCPU>;
using GPUContext = Context<ComputeGPU>;

struct KernelContext {
  CPUContext cpu;
  GPUContext gpu;

  /**
   * @brief Caller-provided allocator for temporary data.
   */
  Scratchpad *scratchpad;
};

}  // namespace kernels
}  // namespace dali

#include "dali/kernels/scratch_copy_impl.h"

#endif  // DALI_KERNELS_CONTEXT_H_

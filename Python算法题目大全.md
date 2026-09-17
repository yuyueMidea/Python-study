# Python 算法题目大全（由易到难，共 24 题）

> 本文整理了 24 道常见的 Python 算法题，按 **简单 → 中等 → 困难** 排列，每道题都包含：
> - 题目描述
> - 解题思路
> - 完整代码（含测试用例）
> - 时间/空间复杂度分析
>
> 建议先自己动手写一遍，再对照答案。

---

## 目录

**一、简单难度**
1. [两数之和](#1-两数之和)
2. [判断回文数](#2-判断回文数)
3. [反转整数](#3-反转整数)
4. [最大公约数](#4-最大公约数)
5. [冒泡排序](#5-冒泡排序)
6. [二分查找](#6-二分查找)
7. [FizzBuzz](#7-fizzbuzz)

**二、中等难度**
8. [快速排序](#8-快速排序)
9. [合并两个有序数组](#9-合并两个有序数组)
10. [最大子数组和（Kadane 算法）](#10-最大子数组和kadane-算法)
11. [有效的括号](#11-有效的括号)
12. [反转链表](#12-反转链表)
13. [最长公共前缀](#13-最长公共前缀)
14. [罗马数字转整数](#14-罗马数字转整数)
15. [二叉树的最大深度](#15-二叉树的最大深度)
16. [三数之和](#16-三数之和)

**三、困难难度**
17. [最长回文子串](#17-最长回文子串)
18. [最长递增子序列](#18-最长递增子序列)
19. [岛屿数量](#19-岛屿数量)
20. [全排列](#20-全排列)
21. [编辑距离](#21-编辑距离)
22. [LRU 缓存机制](#22-lru-缓存机制)
23. [合并 K 个有序链表](#23-合并-k-个有序链表)
24. [0/1 背包问题](#24-01-背包问题)

---

# 一、简单难度

## 1. 两数之和

**题目描述**：给定一个整数数组 `nums` 和一个目标值 `target`，找出数组中和为目标值的两个数的下标。

**思路**：使用哈希表记录"已经出现过的数字 → 下标"，遍历数组时判断 `target - 当前数` 是否已经出现过，一次遍历即可完成，时间复杂度从暴力法的 O(n²) 降到 O(n)。

```python
def two_sum(nums, target):
    seen = {}  # 值 -> 下标
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []

# 测试
print(two_sum([2, 7, 11, 15], 9))   # [0, 1]
print(two_sum([3, 2, 4], 6))        # [1, 2]
```

**复杂度**：时间 O(n)，空间 O(n)。

---

## 2. 判断回文数

**题目描述**：判断一个整数是否是回文数（正读和反读都一样，如 121、1331）。

**思路**：可以转成字符串直接判断，也可以不转字符串，通过反转数字的一半来比较（更省空间，且不使用额外字符串转换）。

```python
def is_palindrome(x):
    # 负数和以 0 结尾但不为 0 的数一定不是回文
    if x < 0 or (x % 10 == 0 and x != 0):
        return False

    reverted = 0
    while x > reverted:
        reverted = reverted * 10 + x % 10
        x //= 10

    # 位数为偶数时 x == reverted；位数为奇数时去掉 reverted 的个位
    return x == reverted or x == reverted // 10

# 测试
print(is_palindrome(121))   # True
print(is_palindrome(-121))  # False
print(is_palindrome(10))    # False
```

**复杂度**：时间 O(log n)（数字位数），空间 O(1)。

---

## 3. 反转整数

**题目描述**：反转一个 32 位有符号整数，如果反转后超出范围则返回 0。

**思路**：不断取出末位数字拼接到结果中，并在每一步检查是否溢出。

```python
def reverse_integer(x):
    INT_MIN, INT_MAX = -2**31, 2**31 - 1
    sign = -1 if x < 0 else 1
    x = abs(x)

    result = 0
    while x != 0:
        digit = x % 10
        x //= 10
        result = result * 10 + digit
        if result > INT_MAX:  # 提前判断溢出
            return 0

    result *= sign
    return result if INT_MIN <= result <= INT_MAX else 0

# 测试
print(reverse_integer(123))    # 321
print(reverse_integer(-123))   # -321
print(reverse_integer(120))    # 21
```

**复杂度**：时间 O(log n)，空间 O(1)。

---

## 4. 最大公约数

**题目描述**：求两个正整数的最大公约数（GCD）。

**思路**：使用**辗转相除法（欧几里得算法）**：`gcd(a, b) = gcd(b, a % b)`，直到余数为 0。

```python
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a

def lcm(a, b):
    """顺带给出最小公倍数"""
    return a * b // gcd(a, b)

# 测试
print(gcd(48, 18))   # 6
print(lcm(4, 6))      # 12
```

**复杂度**：时间 O(log(min(a, b)))，空间 O(1)。

---

## 5. 冒泡排序

**题目描述**：实现冒泡排序算法，对数组进行升序排序。

**思路**：每一轮比较相邻元素，把较大的元素逐步"冒泡"到数组末尾。加入 `swapped` 标志位，若某一轮没有发生交换则说明已经有序，可以提前结束。

```python
def bubble_sort(arr):
    arr = arr[:]  # 拷贝，避免修改原数组
    n = len(arr)
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:  # 已经有序，提前退出
            break
    return arr

# 测试
print(bubble_sort([5, 2, 9, 1, 5, 6]))  # [1, 2, 5, 5, 6, 9]
```

**复杂度**：时间 O(n²)（最好情况 O(n)），空间 O(1)，是**稳定排序**。

---

## 6. 二分查找

**题目描述**：在一个升序数组中查找目标值，返回下标，不存在则返回 -1。

**思路**：维护左右边界 `left, right`，每次取中间值与目标比较，根据大小关系缩小查找范围。

```python
def binary_search(nums, target):
    left, right = 0, len(nums) - 1
    while left <= right:
        mid = (left + right) // 2
        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

# 测试
print(binary_search([1, 3, 5, 7, 9, 11], 7))   # 3
print(binary_search([1, 3, 5, 7, 9, 11], 4))   # -1
```

**复杂度**：时间 O(log n)，空间 O(1)。

---

## 7. FizzBuzz

**题目描述**：打印 1 到 n 的数字，能被 3 整除输出 "Fizz"，能被 5 整除输出 "Buzz"，能同时被 3 和 5 整除输出 "FizzBuzz"，否则输出数字本身。

**思路**：经典的条件判断练习题，注意判断顺序（先判断能否同时被整除）。

```python
def fizz_buzz(n):
    result = []
    for i in range(1, n + 1):
        if i % 15 == 0:
            result.append("FizzBuzz")
        elif i % 3 == 0:
            result.append("Fizz")
        elif i % 5 == 0:
            result.append("Buzz")
        else:
            result.append(str(i))
    return result

# 测试
print(fizz_buzz(15))
# ['1','2','Fizz','4','Buzz','Fizz','7','8','Fizz','Buzz','11','Fizz','13','14','FizzBuzz']
```

**复杂度**：时间 O(n)，空间 O(n)。

---

# 二、中等难度

## 8. 快速排序

**题目描述**：实现快速排序算法。

**思路**：选取一个基准值（pivot），将数组分为比它小和比它大的两部分，递归排序两部分。这里使用列表推导实现的简洁版本（非原地，便于理解）。

```python
def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)

# 原地版本（更省空间，工业界常用）
def quick_sort_inplace(arr, low=0, high=None):
    if high is None:
        high = len(arr) - 1
    if low < high:
        pivot_index = partition(arr, low, high)
        quick_sort_inplace(arr, low, pivot_index - 1)
        quick_sort_inplace(arr, pivot_index + 1, high)
    return arr

def partition(arr, low, high):
    pivot = arr[high]
    i = low - 1
    for j in range(low, high):
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
    arr[i + 1], arr[high] = arr[high], arr[i + 1]
    return i + 1

# 测试
print(quick_sort([5, 2, 9, 1, 5, 6]))          # [1, 2, 5, 5, 6, 9]
print(quick_sort_inplace([5, 2, 9, 1, 5, 6]))  # [1, 2, 5, 5, 6, 9]
```

**复杂度**：平均时间 O(n log n)，最坏 O(n²)（数组已有序且每次选最差 pivot），空间 O(log n)（递归栈）。

---

## 9. 合并两个有序数组

**题目描述**：将两个有序数组 `nums1`（长度为 m+n，后面留有 n 个空位）和 `nums2`（长度为 n）合并为一个有序数组，原地修改 `nums1`。

**思路**：从**后往前**双指针比较，避免覆盖 `nums1` 中还没处理的元素。

```python
def merge(nums1, m, nums2, n):
    i, j, k = m - 1, n - 1, m + n - 1
    while i >= 0 and j >= 0:
        if nums1[i] > nums2[j]:
            nums1[k] = nums1[i]
            i -= 1
        else:
            nums1[k] = nums2[j]
            j -= 1
        k -= 1
    # 如果 nums2 还有剩余，直接填入（nums1 剩余的本来就在正确位置）
    nums1[:j + 1] = nums2[:j + 1]
    return nums1

# 测试
nums1 = [1, 2, 3, 0, 0, 0]
merge(nums1, 3, [2, 5, 6], 3)
print(nums1)  # [1, 2, 2, 3, 5, 6]
```

**复杂度**：时间 O(m + n)，空间 O(1)。

---

## 10. 最大子数组和（Kadane 算法）

**题目描述**：给定一个整数数组，找出和最大的连续子数组，返回其和。

**思路**：动态规划思想——对每个位置，维护"以当前元素结尾的最大子数组和" `cur_sum`。如果之前的和是负数，就丢弃它，从当前元素重新开始。

```python
def max_sub_array(nums):
    max_sum = cur_sum = nums[0]
    for num in nums[1:]:
        cur_sum = max(num, cur_sum + num)  # 要么接上前面，要么重新开始
        max_sum = max(max_sum, cur_sum)
    return max_sum

# 测试
print(max_sub_array([-2, 1, -3, 4, -1, 2, 1, -5, 4]))  # 6，对应子数组 [4, -1, 2, 1]
```

**复杂度**：时间 O(n)，空间 O(1)。

---

## 11. 有效的括号

**题目描述**：给定一个只包含 `()[]{}` 的字符串，判断它是否有效（括号必须以正确的顺序闭合）。

**思路**：使用**栈**。遇到左括号入栈，遇到右括号则检查栈顶是否是对应的左括号，是则弹出，否则无效。

```python
def is_valid(s):
    stack = []
    pairs = {')': '(', ']': '[', '}': '{'}

    for char in s:
        if char in '([{':
            stack.append(char)
        else:  # 右括号
            if not stack or stack[-1] != pairs[char]:
                return False
            stack.pop()

    return not stack  # 栈必须为空才算有效

# 测试
print(is_valid("()[]{}"))   # True
print(is_valid("(]"))       # False
print(is_valid("([)]"))     # False
print(is_valid("{[]}"))     # True
```

**复杂度**：时间 O(n)，空间 O(n)。

---

## 12. 反转链表

**题目描述**：反转一个单链表。

**思路**：迭代法维护三个指针 `prev, cur, next`，每次把当前节点的 `next` 指向前一个节点，逐步反转。

```python
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

def reverse_list(head):
    prev = None
    cur = head
    while cur:
        nxt = cur.next    # 先保存下一个节点
        cur.next = prev    # 反转指针
        prev = cur         # prev 前移
        cur = nxt           # cur 前移
    return prev  # 新的头节点

# 递归版本
def reverse_list_recursive(head):
    if not head or not head.next:
        return head
    new_head = reverse_list_recursive(head.next)
    head.next.next = head
    head.next = None
    return new_head

# 辅助函数：数组 -> 链表 -> 数组，便于测试
def build_list(values):
    dummy = ListNode()
    cur = dummy
    for v in values:
        cur.next = ListNode(v)
        cur = cur.next
    return dummy.next

def list_to_array(head):
    result = []
    while head:
        result.append(head.val)
        head = head.next
    return result

# 测试
head = build_list([1, 2, 3, 4, 5])
print(list_to_array(reverse_list(head)))  # [5, 4, 3, 2, 1]
```

**复杂度**：时间 O(n)，空间 O(1)（迭代）/ O(n)（递归，调用栈）。

---

## 13. 最长公共前缀

**题目描述**：查找字符串数组中的最长公共前缀，如果不存在则返回空字符串。

**思路**：以第一个字符串为基准，逐个字符与其他字符串比较，一旦不匹配就截断。

```python
def longest_common_prefix(strs):
    if not strs:
        return ""

    prefix = strs[0]
    for s in strs[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]  # 逐步缩短前缀
            if not prefix:
                return ""
    return prefix

# 测试
print(longest_common_prefix(["flower", "flow", "flight"]))  # "fl"
print(longest_common_prefix(["dog", "racecar", "car"]))     # ""
```

**复杂度**：时间 O(S)（S 为所有字符总数），空间 O(1)。

---

## 14. 罗马数字转整数

**题目描述**：将罗马数字字符串转换为整数（如 "III" → 3，"IV" → 4，"MCMXCIV" → 1994）。

**思路**：从左到右遍历，如果当前字符代表的数值小于右边字符，则减去当前值（如 IV = 5 - 1），否则加上当前值。

```python
def roman_to_int(s):
    values = {'I': 1, 'V': 5, 'X': 10, 'L': 50,
              'C': 100, 'D': 500, 'M': 1000}

    total = 0
    for i in range(len(s)):
        if i + 1 < len(s) and values[s[i]] < values[s[i + 1]]:
            total -= values[s[i]]
        else:
            total += values[s[i]]
    return total

# 测试
print(roman_to_int("III"))      # 3
print(roman_to_int("IV"))       # 4
print(roman_to_int("MCMXCIV"))  # 1994
```

**复杂度**：时间 O(n)，空间 O(1)。

---

## 15. 二叉树的最大深度

**题目描述**：给定一棵二叉树，求它的最大深度（根节点到最远叶子节点的路径上节点数）。

**思路**：递归——树的深度 = 1 + max(左子树深度, 右子树深度)。也可以用 BFS 逐层遍历。

```python
class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

# 递归解法
def max_depth(root):
    if not root:
        return 0
    return 1 + max(max_depth(root.left), max_depth(root.right))

# BFS 迭代解法
from collections import deque

def max_depth_bfs(root):
    if not root:
        return 0
    queue = deque([root])
    depth = 0
    while queue:
        depth += 1
        for _ in range(len(queue)):  # 处理当前层的所有节点
            node = queue.popleft()
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
    return depth

# 测试： 构造一棵树   3
#                   / \
#                  9  20
#                     /  \
#                    15   7
root = TreeNode(3, TreeNode(9), TreeNode(20, TreeNode(15), TreeNode(7)))
print(max_depth(root))       # 3
print(max_depth_bfs(root))   # 3
```

**复杂度**：时间 O(n)，空间 O(h)（h 为树高，递归栈）或 O(n)（BFS 队列）。

---

## 16. 三数之和

**题目描述**：给定一个整数数组，找出所有和为 0 且不重复的三元组。

**思路**：先排序，固定第一个数，用**双指针**在剩余部分寻找另外两个数，注意跳过重复元素避免重复解。

```python
def three_sum(nums):
    nums.sort()
    n = len(nums)
    result = []

    for i in range(n - 2):
        if nums[i] > 0:  # 排序后最小的数都大于0，不可能凑出0
            break
        if i > 0 and nums[i] == nums[i - 1]:  # 跳过重复的第一个数
            continue

        left, right = i + 1, n - 1
        while left < right:
            total = nums[i] + nums[left] + nums[right]
            if total == 0:
                result.append([nums[i], nums[left], nums[right]])
                while left < right and nums[left] == nums[left + 1]:
                    left += 1  # 跳过重复
                while left < right and nums[right] == nums[right - 1]:
                    right -= 1  # 跳过重复
                left += 1
                right -= 1
            elif total < 0:
                left += 1
            else:
                right -= 1

    return result

# 测试
print(three_sum([-1, 0, 1, 2, -1, -4]))
# [[-1, -1, 2], [-1, 0, 1]]
```

**复杂度**：时间 O(n²)，空间 O(log n)~O(n)（排序所需）。

---

# 三、困难难度

## 17. 最长回文子串

**题目描述**：给定一个字符串，找出其中最长的回文子串。

**思路**：**中心扩展法**——回文串一定关于某个中心对称，中心可能是一个字符（奇数长度）或两个字符之间（偶数长度），对每个可能的中心向两边扩展。

```python
def longest_palindrome(s):
    if not s:
        return ""

    def expand_around_center(left, right):
        while left >= 0 and right < len(s) and s[left] == s[right]:
            left -= 1
            right += 1
        return s[left + 1:right]  # 返回实际的回文子串

    result = ""
    for i in range(len(s)):
        odd = expand_around_center(i, i)        # 奇数长度，中心是 s[i]
        even = expand_around_center(i, i + 1)    # 偶数长度，中心在 s[i] 和 s[i+1] 之间
        longer = odd if len(odd) > len(even) else even
        if len(longer) > len(result):
            result = longer

    return result

# 测试
print(longest_palindrome("babad"))  # "bab" 或 "aba"
print(longest_palindrome("cbbd"))   # "bb"
```

**复杂度**：时间 O(n²)，空间 O(1)（不计返回结果）。

> 进阶：还可以用 **动态规划 O(n²)** 或 **Manacher 算法 O(n)** 求解，Manacher 是面试中的加分项，感兴趣可以进一步研究。

---

## 18. 最长递增子序列

**题目描述**：给定一个无序整数数组，找出其中最长严格递增子序列的长度。

**思路**：
- **动态规划 O(n²)**：`dp[i]` 表示以 `nums[i]` 结尾的最长递增子序列长度。
- **贪心 + 二分查找 O(n log n)**：维护一个数组 `tails`，`tails[i]` 表示长度为 `i+1` 的递增子序列的最小可能结尾值。

```python
# 方法一：动态规划 O(n^2)
def length_of_lis_dp(nums):
    if not nums:
        return 0
    dp = [1] * len(nums)
    for i in range(len(nums)):
        for j in range(i):
            if nums[j] < nums[i]:
                dp[i] = max(dp[i], dp[j] + 1)
    return max(dp)

# 方法二：贪心 + 二分查找 O(n log n)
import bisect

def length_of_lis(nums):
    tails = []
    for num in nums:
        pos = bisect.bisect_left(tails, num)  # 找到第一个 >= num 的位置
        if pos == len(tails):
            tails.append(num)  # num 比所有元素都大，扩展序列
        else:
            tails[pos] = num   # 替换，保持 tails 尽可能小
    return len(tails)

# 测试
print(length_of_lis_dp([10, 9, 2, 5, 3, 7, 101, 18]))  # 4  ([2,3,7,101] 或 [2,3,7,18])
print(length_of_lis([10, 9, 2, 5, 3, 7, 101, 18]))     # 4
```

**复杂度**：DP 解法时间 O(n²)、空间 O(n)；贪心+二分解法时间 O(n log n)、空间 O(n)。

---

## 19. 岛屿数量

**题目描述**：给定一个由 `'1'`（陆地）和 `'0'`（水）组成的二维网格，计算岛屿的数量（岛屿由水平/垂直相邻的陆地连接而成）。

**思路**：遍历网格，遇到陆地就用 **DFS 或 BFS** 把与它相连的所有陆地"淹没"（标记为已访问），每次触发一次遍历就说明发现了一个新岛屿，计数加一。

```python
def num_islands(grid):
    if not grid:
        return 0

    rows, cols = len(grid), len(grid[0])
    grid = [row[:] for row in grid]  # 拷贝，避免修改原数据

    def dfs(r, c):
        # 越界或者是水/已访问，直接返回
        if r < 0 or r >= rows or c < 0 or c >= cols or grid[r][c] != '1':
            return
        grid[r][c] = '0'  # 标记为已访问（淹没）
        dfs(r + 1, c)
        dfs(r - 1, c)
        dfs(r, c + 1)
        dfs(r, c - 1)

    count = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == '1':
                count += 1
                dfs(r, c)  # 淹没整个岛屿
    return count

# 测试
grid = [
    ["1", "1", "0", "0", "0"],
    ["1", "1", "0", "0", "0"],
    ["0", "0", "1", "0", "0"],
    ["0", "0", "0", "1", "1"]
]
print(num_islands(grid))  # 3
```

**复杂度**：时间 O(rows × cols)，空间 O(rows × cols)（最坏情况下递归栈深度）。

---

## 20. 全排列

**题目描述**：给定一个不含重复数字的数组，返回其所有可能的全排列。

**思路**：**回溯法**——每一步从剩余未使用的数字中选一个放入当前路径，递归处理下一位，处理完后撤销选择（回溯），尝试其他可能。

```python
def permute(nums):
    result = []
    path = []
    used = [False] * len(nums)

    def backtrack():
        if len(path) == len(nums):
            result.append(path[:])  # 拷贝当前路径
            return

        for i in range(len(nums)):
            if used[i]:
                continue
            # 做选择
            path.append(nums[i])
            used[i] = True
            # 递归
            backtrack()
            # 撤销选择（回溯）
            path.pop()
            used[i] = False

    backtrack()
    return result

# 测试
print(permute([1, 2, 3]))
# [[1,2,3],[1,3,2],[2,1,3],[2,3,1],[3,1,2],[3,2,1]]
```

**复杂度**：时间 O(n × n!)，空间 O(n)（递归栈，不计结果存储）。

---

## 21. 编辑距离

**题目描述**：给定两个字符串 `word1` 和 `word2`，计算将 `word1` 转换成 `word2` 所需的最少操作数（插入、删除、替换一个字符）。

**思路**：经典**二维动态规划**。`dp[i][j]` 表示 `word1` 前 `i` 个字符转换成 `word2` 前 `j` 个字符所需的最少操作数：
- 如果末尾字符相同：`dp[i][j] = dp[i-1][j-1]`
- 否则取插入、删除、替换三种操作中的最小值 + 1

```python
def min_distance(word1, word2):
    m, n = len(word1), len(word2)
    # dp[i][j]: word1[:i] -> word2[:j] 的最少编辑次数
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # 边界：word1 为空，需要插入 j 次；word2 为空，需要删除 i 次
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if word1[i - 1] == word2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]  # 字符相同，不需要操作
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],      # 删除 word1[i-1]
                    dp[i][j - 1],      # 插入 word2[j-1]
                    dp[i - 1][j - 1]   # 替换 word1[i-1] 为 word2[j-1]
                )
    return dp[m][n]

# 测试
print(min_distance("horse", "ros"))    # 3
print(min_distance("intention", "execution"))  # 5
```

**复杂度**：时间 O(m × n)，空间 O(m × n)（可以优化到 O(n)，用滚动数组）。

---

## 22. LRU 缓存机制

**题目描述**：设计一个 LRU（最近最少使用）缓存，支持 `get(key)` 和 `put(key, value)` 操作，超出容量时淘汰最久未使用的数据，要求两个操作都是 **O(1)** 时间复杂度。

**思路**：Python 中 `OrderedDict` 天然支持"按插入/访问顺序排列"并可以 O(1) 移动元素到末尾，非常适合实现 LRU。也可以用**哈希表 + 双向链表**手写实现（面试中常考手写版本）。

```python
from collections import OrderedDict

# 方法一：使用 OrderedDict（简洁写法）
class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = OrderedDict()

    def get(self, key):
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)  # 标记为最近使用
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # 淘汰最久未使用（队首）


# 方法二：手写哈希表 + 双向链表（面试常考，展示原理）
class Node:
    def __init__(self, key=0, value=0):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None

class LRUCacheManual:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = {}  # key -> Node
        # 使用哨兵节点简化边界处理
        self.head = Node()
        self.tail = Node()
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev

    def _add_to_front(self, node):
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def get(self, key):
        if key not in self.cache:
            return -1
        node = self.cache[key]
        self._remove(node)
        self._add_to_front(node)  # 移到最前面（最近使用）
        return node.value

    def put(self, key, value):
        if key in self.cache:
            self._remove(self.cache[key])
        node = Node(key, value)
        self.cache[key] = node
        self._add_to_front(node)

        if len(self.cache) > self.capacity:
            lru = self.tail.prev  # 最久未使用的节点（在末尾）
            self._remove(lru)
            del self.cache[lru.key]

# 测试
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
print(cache.get(1))   # 1
cache.put(3, 3)        # 淘汰 key=2
print(cache.get(2))   # -1
cache.put(4, 4)        # 淘汰 key=1
print(cache.get(1))   # -1
print(cache.get(3))   # 3
print(cache.get(4))   # 4
```

**复杂度**：`get` 和 `put` 均为时间 O(1)，空间 O(capacity)。

---

## 23. 合并 K 个有序链表

**题目描述**：给定 `k` 个升序链表，将它们合并为一个升序链表。

**思路**：**优先队列（最小堆）**——把每个链表当前的头节点放入堆中，每次弹出最小值接到结果链表后面，再把该节点的下一个节点放入堆中，循环直到堆为空。

```python
import heapq

class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

    def __lt__(self, other):  # 堆需要比较节点，这里按 val 比较
        return self.val < other.val

def merge_k_lists(lists):
    heap = []
    # 把每个链表的头节点放入堆
    for node in lists:
        if node:
            heapq.heappush(heap, node)

    dummy = ListNode()
    cur = dummy

    while heap:
        smallest = heapq.heappop(heap)
        cur.next = smallest
        cur = cur.next
        if smallest.next:
            heapq.heappush(heap, smallest.next)

    return dummy.next

# 辅助函数
def build_list(values):
    dummy = ListNode()
    cur = dummy
    for v in values:
        cur.next = ListNode(v)
        cur = cur.next
    return dummy.next

def list_to_array(head):
    result = []
    while head:
        result.append(head.val)
        head = head.next
    return result

# 测试
lists = [build_list([1, 4, 5]), build_list([1, 3, 4]), build_list([2, 6])]
merged = merge_k_lists(lists)
print(list_to_array(merged))  # [1, 1, 2, 3, 4, 4, 5, 6]
```

**复杂度**：时间 O(N log k)（N 为所有节点总数，k 为链表个数），空间 O(k)（堆的大小）。

---

## 24. 0/1 背包问题

**题目描述**：给定 `n` 件物品，每件物品有重量 `weight[i]` 和价值 `value[i]`，背包容量为 `capacity`，每件物品只能选或不选一次，求能装下的最大总价值。

**思路**：经典**动态规划**问题。`dp[i][w]` 表示前 `i` 件物品在容量为 `w` 时能获得的最大价值。对第 `i` 件物品，要么不选（`dp[i-1][w]`），要么选（前提是 `w >= weight[i-1]`，此时价值为 `dp[i-1][w-weight[i-1]] + value[i-1]`），取两者较大值。可以用一维数组滚动优化空间。

```python
def knapsack_01(weights, values, capacity):
    n = len(weights)
    # 二维 DP（便于理解）
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        for w in range(capacity + 1):
            dp[i][w] = dp[i - 1][w]  # 不选第 i 件物品
            if w >= weights[i - 1]:  # 能放下才考虑选
                dp[i][w] = max(dp[i][w],
                                dp[i - 1][w - weights[i - 1]] + values[i - 1])
    return dp[n][capacity]


# 空间优化版：一维滚动数组 O(capacity)
def knapsack_01_optimized(weights, values, capacity):
    n = len(weights)
    dp = [0] * (capacity + 1)

    for i in range(n):
        # 容量必须从大到小遍历，避免同一件物品被重复选取（0/1背包核心技巧）
        for w in range(capacity, weights[i] - 1, -1):
            dp[w] = max(dp[w], dp[w - weights[i]] + values[i])
    return dp[capacity]

# 测试
weights = [2, 3, 4, 5]
values = [3, 4, 5, 6]
capacity = 8
print(knapsack_01(weights, values, capacity))            # 10
print(knapsack_01_optimized(weights, values, capacity))  # 10
```

**复杂度**：时间 O(n × capacity)，二维空间 O(n × capacity)，优化后空间 O(capacity)。

---

## 总结

| 难度 | 涉及知识点 |
|---|---|
| 简单 | 哈希表、双指针、数学、基础排序、二分查找 |
| 中等 | 快排、栈、链表、双指针、动态规划入门 |
| 困难 | 中心扩展、DFS/BFS、回溯、二维动态规划、堆、01背包 |

刷题建议：
1. 先独立思考 5-10 分钟，再看思路提示。
2. 同一道题尝试用**不同的方法**（如暴力法 vs 优化解法）加深理解。
3. 做完记得分析**时间/空间复杂度**，这是面试中经常被追问的点。
4. 定期回顾做过的题目，尤其是动态规划和回溯类的"模板题"。

祝刷题顺利 🎉

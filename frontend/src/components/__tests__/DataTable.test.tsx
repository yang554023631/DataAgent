import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DataTable } from '../DataTable'

describe('DataTable', () => {
  const mockColumns = ['名称', '点击量', '花费']
  const mockRows = [
    ['渠道A', 1000, 5000],
    ['渠道B', 2000, 8000],
    ['渠道C', 1500, 6000],
    ['渠道D', 3000, 10000],
    ['渠道E', 2500, 9000],
  ]

  describe('基础渲染', () => {
    it('应该正确渲染列名', () => {
      render(<DataTable columns={mockColumns} rows={mockRows} />)

      mockColumns.forEach(col => {
        expect(screen.getByText(col)).toBeInTheDocument()
      })
    })

    it('应该正确渲染数据行', () => {
      render(<DataTable columns={mockColumns} rows={mockRows} />)

      expect(screen.getByText('渠道A')).toBeInTheDocument()
      expect(screen.getByText('渠道B')).toBeInTheDocument()
      expect(screen.getByText('1,000')).toBeInTheDocument()
      expect(screen.getByText('2,000')).toBeInTheDocument()
    })

    it('空数据应该正常渲染表头', () => {
      render(<DataTable columns={mockColumns} rows={[]} />)

      mockColumns.forEach(col => {
        expect(screen.getByText(col)).toBeInTheDocument()
      })
    })
  })

  describe('分页功能', () => {
    it('只要有数据就显示页面大小选择器（即使只有一页）', () => {
      // 50 条数据，每页 50 条，刚好一页 - 修复前 Bug：选择器会消失
      const fiftyRows = Array.from({ length: 50 }, (_, i) => [`渠道${i + 1}`, i * 100, i * 500])
      render(<DataTable columns={mockColumns} rows={fiftyRows} pageSize={50} />)

      // 页面大小选择器应该显示
      expect(screen.getByRole('combobox')).toBeInTheDocument()
      // 总条数应该显示（使用部分匹配）
      expect(screen.getByText(/共 50 条/)).toBeInTheDocument()
      // 页码导航按钮不应该显示（只有一页）
      expect(screen.queryByText('首页')).not.toBeInTheDocument()
      expect(screen.queryByText('下一页')).not.toBeInTheDocument()
    })

    it('数据少于10条时仍然显示页面大小选择器', () => {
      render(<DataTable columns={mockColumns} rows={mockRows.slice(0, 5)} />)

      // 页面大小选择器应该始终显示
      expect(screen.getByRole('combobox')).toBeInTheDocument()
      expect(screen.getByText(/共 5 条/)).toBeInTheDocument()
      // 但页码按钮不显示
      expect(screen.queryByText('首页')).not.toBeInTheDocument()
    })

    it('数据多于10条时显示分页控件', () => {
      const manyRows = Array.from({ length: 15 }, (_, i) => [`渠道${i + 1}`, i * 100, i * 500])
      render(<DataTable columns={mockColumns} rows={manyRows} />)

      expect(screen.getByText('首页')).toBeInTheDocument()
      expect(screen.getByText('上一页')).toBeInTheDocument()
      expect(screen.getByText('下一页')).toBeInTheDocument()
      expect(screen.getByText('末页')).toBeInTheDocument()
    })

    it('点击下一页应该显示下一页数据', () => {
      const manyRows = Array.from({ length: 15 }, (_, i) => [`渠道${i + 1}`, i * 100, i * 500])
      render(<DataTable columns={mockColumns} rows={manyRows} />)

      expect(screen.getByText('渠道1')).toBeInTheDocument()
      expect(screen.queryByText('渠道11')).not.toBeInTheDocument()

      fireEvent.click(screen.getByText('下一页'))

      expect(screen.queryByText('渠道1')).not.toBeInTheDocument()
      expect(screen.getByText('渠道11')).toBeInTheDocument()
    })

    it('第一页时上一页按钮应该禁用', () => {
      const manyRows = Array.from({ length: 15 }, (_, i) => [`渠道${i + 1}`, i * 100, i * 500])
      render(<DataTable columns={mockColumns} rows={manyRows} />)

      expect(screen.getByText('上一页')).toBeDisabled()
      expect(screen.getByText('首页')).toBeDisabled()
    })

    it('最后一页时下一页按钮应该禁用', () => {
      const manyRows = Array.from({ length: 15 }, (_, i) => [`渠道${i + 1}`, i * 100, i * 500])
      render(<DataTable columns={mockColumns} rows={manyRows} />)

      fireEvent.click(screen.getByText('末页'))

      expect(screen.getByText('下一页')).toBeDisabled()
      expect(screen.getByText('末页')).toBeDisabled()
    })
  })

  describe('页面大小选择器', () => {
    it('应该显示所有页面大小选项', () => {
      const manyRows = Array.from({ length: 100 }, (_, i) => [`渠道${i + 1}`, i * 100, i * 500])
      render(<DataTable columns={mockColumns} rows={manyRows} />)

      const select = screen.getByRole('combobox')
      expect(select).toBeInTheDocument()

      const options = Array.from(select.querySelectorAll('option'))
      expect(options.map(o => o.value)).toEqual(['10', '20', '50', '100'])
    })

    it('切换页面大小应该重置到第一页', () => {
      const manyRows = Array.from({ length: 30 }, (_, i) => [`渠道${i + 1}`, i * 100, i * 500])
      render(<DataTable columns={mockColumns} rows={manyRows} />)

      fireEvent.click(screen.getByText('下一页'))
      expect(screen.getByText('渠道11')).toBeInTheDocument()

      fireEvent.change(screen.getByRole('combobox'), { target: { value: '20' } })

      expect(screen.getByText('渠道1')).toBeInTheDocument()
    })
  })

  describe('页码跳转功能', () => {
    it('应该显示页码跳转输入框', () => {
      const manyRows = Array.from({ length: 30 }, (_, i) => [`渠道${i + 1}`, i * 100, i * 500])
      render(<DataTable columns={mockColumns} rows={manyRows} />)

      expect(screen.getByPlaceholderText('页码')).toBeInTheDocument()
      expect(screen.getByText('跳转')).toBeInTheDocument()
    })

    it('输入有效页码应该跳转到对应页', () => {
      const manyRows = Array.from({ length: 30 }, (_, i) => [`渠道${i + 1}`, i * 100, i * 500])
      render(<DataTable columns={mockColumns} rows={manyRows} />)

      const input = screen.getByPlaceholderText('页码')
      fireEvent.change(input, { target: { value: '2' } })
      fireEvent.click(screen.getByText('跳转'))

      expect(screen.getByText('渠道11')).toBeInTheDocument()
    })

    it('按 Enter 键应该跳转到对应页', () => {
      const manyRows = Array.from({ length: 30 }, (_, i) => [`渠道${i + 1}`, i * 100, i * 500])
      render(<DataTable columns={mockColumns} rows={manyRows} />)

      const input = screen.getByPlaceholderText('页码')
      fireEvent.change(input, { target: { value: '2' } })
      fireEvent.keyPress(input, { key: 'Enter', charCode: 13, code: 'Enter' })

      expect(screen.getByText('渠道11')).toBeInTheDocument()
    })
  })

  describe('分页信息', () => {
    it('应该显示正确的总数和页码信息', () => {
      const manyRows = Array.from({ length: 25 }, (_, i) => [`渠道${i + 1}`, i * 100, i * 500])
      render(<DataTable columns={mockColumns} rows={manyRows} />)

      expect(screen.getByText(/共 25 条/)).toBeInTheDocument()
      expect(screen.getByText(/第 1 \/ 3 页/)).toBeInTheDocument()
    })
  })

  describe('排序功能', () => {
    it('点击表头第一次应该按升序排序', () => {
      render(<DataTable columns={mockColumns} rows={mockRows} />)

      // 点击"点击量"表头
      fireEvent.click(screen.getByText('点击量'))

      // 按点击量升序排列：渠道A(1000) -> 渠道C(1500) -> 渠道B(2000)
      const allRows = screen.getAllByText(/渠道[ABCD]/)
      expect(allRows[0]).toHaveTextContent('渠道A')
      expect(allRows[1]).toHaveTextContent('渠道C')
      expect(allRows[2]).toHaveTextContent('渠道B')
    })

    it('点击表头第二次应该按降序排序', () => {
      render(<DataTable columns={mockColumns} rows={mockRows} />)

      // 点击两次"点击量"表头
      fireEvent.click(screen.getByText('点击量'))
      fireEvent.click(screen.getByText('点击量'))

      // 按点击量降序排列：渠道D(3000) -> 渠道E(2500) -> 渠道B(2000)
      const allRows = screen.getAllByText(/渠道[ABCDE]/)
      expect(allRows[0]).toHaveTextContent('渠道D')
      expect(allRows[1]).toHaveTextContent('渠道E')
      expect(allRows[2]).toHaveTextContent('渠道B')
    })

    it('点击表头第三次应该取消排序', () => {
      render(<DataTable columns={mockColumns} rows={mockRows} />)

      // 点击三次"点击量"表头
      fireEvent.click(screen.getByText('点击量'))  // 升序
      fireEvent.click(screen.getByText('点击量'))  // 降序
      fireEvent.click(screen.getByText('点击量'))  // 取消排序

      // 恢复原始顺序
      const allRows = screen.getAllByText(/渠道[ABCD]/)
      expect(allRows[0]).toHaveTextContent('渠道A')
      expect(allRows[1]).toHaveTextContent('渠道B')
      expect(allRows[2]).toHaveTextContent('渠道C')
    })

    it('排序后应该重置到第一页', () => {
      const manyRows = Array.from({ length: 15 }, (_, i) => [`渠道${i + 1}`, i * 100, i * 500])
      render(<DataTable columns={mockColumns} rows={manyRows} />)

      // 先到第二页
      fireEvent.click(screen.getByText('下一页'))
      expect(screen.getByText('渠道11')).toBeInTheDocument()

      // 点击表头排序
      fireEvent.click(screen.getByText('点击量'))

      // 应该回到第一页
      expect(screen.getByText('渠道1')).toBeInTheDocument()
      expect(screen.queryByText('渠道11')).not.toBeInTheDocument()
    })

    it('字符串列应该支持中文拼音排序', () => {
      const chineseRows = [
        ['北京', 1000, 5000],
        ['上海', 2000, 8000],
        ['广州', 1500, 6000],
        ['深圳', 3000, 10000],
      ]
      render(<DataTable columns={['城市', '点击量', '花费']} rows={chineseRows} />)

      // 点击城市表头排序
      fireEvent.click(screen.getByText('城市'))

      // 按拼音排序：北京(B) -> 广州(G) -> 上海(S) -> 深圳(S)
      const allRows = screen.getAllByRole('row')
      // 第一行是表头，所以数据行从索引1开始
      expect(allRows[1]).toHaveTextContent('北京')
      expect(allRows[2]).toHaveTextContent('广州')
      expect(allRows[3]).toHaveTextContent('上海')
      expect(allRows[4]).toHaveTextContent('深圳')
    })
  })
})

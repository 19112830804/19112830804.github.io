import { createClient } from '@supabase/supabase-js';

// 初始化 Supabase 客户端
const supabase = createClient(
  'https://your-project-id.supabase.co',  // 从 Supabase 项目设置中获取
  'your-anon-key'                         // 从 Supabase 项目设置中获取
);

// 生成唯一取件码（格式：FV-XXXXXX）
function generateCode() {
  return 'FV-' + Math.random().toString(36).substr(2, 6).toUpperCase();
}

// 文件上传函数
export async function uploadFile(file) {
  try {
    // 生成取件码
    const code = generateCode();
    
    // 构建存储路径（格式：uploads/FV-XXXXXX_原始文件名）
    const filePath = `uploads/${code}_${file.name}`;
    
    // 上传文件到 Supabase 存储
    const { error: uploadError } = await supabase.storage
      .from('uploads')
      .upload(filePath, file);
    
    if (uploadError) {
      console.error('文件上传失败:', uploadError);
      return null;
    }
    
    // 获取文件的公开 URL
    const { publicUrl } = supabase.storage
      .from('uploads')
      .getPublicUrl(filePath);
    
    // 计算过期时间（7天后）
    const expireDate = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
    
    // 将文件元数据保存到数据库
    const { error: dbError } = await supabase
      .from('files')
      .insert([{
        code,
        name: file.name,
        url: publicUrl,
        size: file.size,
        expire_date: expireDate
      }]);
    
    if (dbError) {
      console.error('保存元数据失败:', dbError);
      // 上传成功但元数据保存失败，删除已上传的文件
      await supabase.storage.from('uploads').remove([filePath]);
      return null;
    }
    
    // 返回成功结果
    return { 
      code,
      name: file.name,
      url: publicUrl,
      size: file.size,
      uploadDate: new Date().toISOString(),
      expireDate: expireDate.toISOString()
    };
  } catch (error) {
    console.error('上传过程发生错误:', error);
    return null;
  }
}

// 根据取件码获取文件信息
export async function getFile(code) {
  try {
    // 从数据库查询文件信息
    const { data, error } = await supabase
      .from('files')
      .select('*')
      .eq('code', code)
      .single();
    
    if (error) {
      console.error('查询文件失败:', error);
      return null;
    }
    
    // 检查文件是否过期
    if (new Date(data.expire_date) < new Date()) {
      // 文件已过期，删除文件和元数据
      await supabase.storage.from('uploads').remove([data.url.split('/').pop()]);
      await supabase.from('files').delete().eq('code', code);
      return null;
    }
    
    return data;
  } catch (error) {
    console.error('获取文件时发生错误:', error);
    return null;
  }
}
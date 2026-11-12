// Initialize Vue before Element Plus when this service is the first imported UI module.
import 'vue';
import { ElMessageBox } from 'element-plus';

export async function confirmAction(message) {
  try {
    await ElMessageBox.confirm(message, '确认操作', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      closeOnClickModal: false,
      distinguishCancelAndClose: true,
    });
    return true;
  } catch (reason) {
    if (reason === 'cancel' || reason === 'close') return false;
    throw reason;
  }
}

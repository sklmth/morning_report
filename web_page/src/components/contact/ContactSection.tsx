import { useState, type FormEvent } from 'react';
import { CheckCircle2, Github, Mail, MapPin, Send } from 'lucide-react';
import { contactProfile } from '@/content/siteContent';
import { Reveal } from '@/components/common/Reveal';
import { Button } from '@/components/common/Button';

type FormState = { name: string; email: string; topic: string; message: string };
type FormErrors = Partial<Record<keyof FormState, string>>;

const initialForm: FormState = { name: '', email: '', topic: '', message: '' };

function getErrors(form: FormState): FormErrors {
  const errors: FormErrors = {};
  if (!form.name.trim()) errors.name = '请填写你的名字。';
  if (!form.email.trim()) errors.email = '请填写邮箱。';
  else if (!/^\S+@\S+\.\S+$/.test(form.email)) errors.email = '请输入有效的邮箱地址。';
  if (!form.topic.trim()) errors.topic = '请填写主题。';
  if (!form.message.trim()) errors.message = '请留下一段简短消息。';
  return errors;
}

export function ContactSection() {
  const [form, setForm] = useState<FormState>(initialForm);
  const [errors, setErrors] = useState<FormErrors>({});
  const [sent, setSent] = useState(false);
  const mailto = `mailto:${contactProfile.email}?subject=${encodeURIComponent(form.topic || '来自 Morning Atlas 的一封留言')}&body=${encodeURIComponent(`姓名：${form.name}\n邮箱：${form.email}\n\n${form.message}`)}`;

  const updateField = (field: keyof FormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setSent(false);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors = getErrors(form);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    setSent(true);
  };

  return (
    <section className="section contact-section" id="contact">
      <div className="section-inner">
        <div className="contact-intro-grid">
          <Reveal><div><p className="eyebrow">06 / 保持联系</p><h2 className="display contact-title">留下一段信号。</h2><p className="section-intro">有趣的路线、歌单、协作项目，或者只是想分享一段夜路，都欢迎发来。</p></div></Reveal>
          <Reveal><aside className="contact-profile"><span className="contact-availability"><CheckCircle2 size={15} aria-hidden="true" /> {contactProfile.availability}</span>{contactProfile.channels.map((channel) => <div className="contact-channel" key={channel.label}>{channel.label === '邮箱' ? <Mail size={16} aria-hidden="true" /> : channel.label === 'GitHub' ? <Github size={16} aria-hidden="true" /> : <MapPin size={16} aria-hidden="true" />}{channel.href ? <a href={channel.href} target={channel.href.startsWith('http') ? '_blank' : undefined} rel={channel.href.startsWith('http') ? 'noreferrer' : undefined}>{channel.value}</a> : <span>{channel.value}</span>}</div>)}</aside></Reveal>
        </div>
        <Reveal><div className="contact-form-wrap"><form className="contact-form" noValidate onSubmit={handleSubmit}><div className="contact-form-grid"><label>姓名<input value={form.name} onChange={(event) => updateField('name', event.target.value)} aria-invalid={Boolean(errors.name)} aria-describedby={errors.name ? 'contact-name-error' : undefined} />{errors.name && <small id="contact-name-error">{errors.name}</small>}</label><label>邮箱<input type="email" value={form.email} onChange={(event) => updateField('email', event.target.value)} aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? 'contact-email-error' : undefined} />{errors.email && <small id="contact-email-error">{errors.email}</small>}</label></div><label>主题<input value={form.topic} onChange={(event) => updateField('topic', event.target.value)} aria-invalid={Boolean(errors.topic)} aria-describedby={errors.topic ? 'contact-topic-error' : undefined} />{errors.topic && <small id="contact-topic-error">{errors.topic}</small>}</label><label>留言<textarea rows={5} value={form.message} onChange={(event) => updateField('message', event.target.value)} aria-invalid={Boolean(errors.message)} aria-describedby={errors.message ? 'contact-message-error' : undefined} />{errors.message && <small id="contact-message-error">{errors.message}</small>}</label><div className="contact-actions"><Button variant="primary" type="submit"><Send size={16} aria-hidden="true" /> 发送留言</Button><a className="button" href={mailto}><Mail size={16} aria-hidden="true" /> 打开邮件客户端</a></div>{sent && <p className="contact-success" role="status"><CheckCircle2 size={17} aria-hidden="true" /> 留言已保存到本地演示状态。请使用邮件操作真正发送。</p>}</form></div></Reveal>
      </div>
    </section>
  );
}
